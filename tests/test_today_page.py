"""Looking Back — the page's own guarantees (R-428 … R-431).

The page reads four serving views and does no arithmetic on the numbers it ranks. These tests
pin the two things that would be silently wrong rather than loud: the grain under a summing
leaderboard, and the poll delta for a team with no previous rank.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / "site" / "views" / "today.py"
SOURCE = TODAY.read_text()


# --- the grain under a summing leaderboard --------------------------------------------

def _duplicate_keys(frame: pd.DataFrame) -> pd.DataFrame:
    """The leaderboard's grain rule, as a function so a test can feed it a bad frame.

    Mirrors assert_srv_player_game_log_is_one_row_per_player_stat, which runs against real
    data and therefore cannot be observed failing until real data breaks.
    """
    keys = ["game_id", "player_id", "stat_category", "stat_type"]
    counts = frame.groupby(keys).size().reset_index(name="rows_found")
    return counts[counts["rows_found"] > 1]


def _clean_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"game_id": 1, "player_id": "a", "stat_category": "rushing", "stat_type": "YDS",
         "stat_value": 100},
        {"game_id": 1, "player_id": "b", "stat_category": "rushing", "stat_type": "YDS",
         "stat_value": 80},
        {"game_id": 2, "player_id": "a", "stat_category": "rushing", "stat_type": "YDS",
         "stat_value": 60},
    ])


def test_the_grain_guard_passes_on_clean_data():
    assert _duplicate_keys(_clean_frame()).empty


def test_the_grain_guard_FAILS_on_a_simulated_duplicate():
    """PROVEN RED. A guard never seen rejecting anything is a guard nobody has tested.

    This is the exact shape A060 found in production: the same athlete listed twice for one
    game, one category, one stat type — identical values, so a top-N by max is unaffected and
    a SUM is inflated by exactly one player's contribution.
    """
    dirty = pd.concat([_clean_frame(), _clean_frame().iloc[[0]]], ignore_index=True)
    found = _duplicate_keys(dirty)
    assert len(found) == 1, f"the duplicate was not caught:\n{found}"
    assert int(found.iloc[0]["rows_found"]) == 2
    # And the failure mode it protects against, demonstrated rather than asserted in prose:
    assert dirty["stat_value"].sum() == 340, "the duplicate inflates the sum"
    assert _clean_frame()["stat_value"].sum() == 240, "the true total"


def test_the_dbt_test_exists_on_the_serving_view():
    """The unit test above is the observable half; this is the half that sees real data."""
    sql = ROOT / "dbt" / "tests" / "assert_srv_player_game_log_is_one_row_per_player_stat.sql"
    assert sql.exists()
    body = sql.read_text()
    assert "srv_player_game_log" in body
    assert "having count(*) > 1" in body
    assert "severity='error'" in body


# --- the page's contract ---------------------------------------------------------------

def test_no_metric_maths_on_the_ranking_columns():
    """The page orders rows; it does not compute what it ranks on.

    `spread_favorite_side`, `favorite_covered` and `actual_margin` are carried by srv_game
    precisely so Streamlit does not re-derive a favourite. R-393 measured 2 of 114 games where
    the spread and moneyline disagree, so a re-derivation here would silently differ from the
    warehouse.
    """
    for column in ("spread_favorite_side", "moneyline_favorite_side", "actual_margin",
                   "favorite_covered"):
        assert column in SOURCE, f"{column} should be read from the view"
    # The tell-tale of re-derivation: comparing a spread to zero to decide a favourite.
    assert not re.search(r"spread\w*\s*[<>]\s*0", SOURCE), \
        "the page appears to derive a favourite from the sign of the spread"


def test_every_query_reads_one_relation_and_caps_its_rows():
    """G-2 and the LIMIT rule, checked on this file rather than trusted."""
    queries = re.findall(r'"""\s*(select\b.*?)"""', SOURCE, re.DOTALL | re.IGNORECASE)
    assert len(queries) >= 4, f"expected four panel queries, found {len(queries)}"
    for sql in queries:
        flat = " ".join(sql.split())
        assert not re.search(r"\bjoin\b", flat, re.IGNORECASE), f"join in: {flat[:70]}"
        assert re.search(r"\blimit\s+(\d+|\{DEPTH\})", flat, re.IGNORECASE), \
            f"no literal limit in: {flat[:70]}"


def test_the_week_floor_is_named_not_hardcoded_in_copy():
    """Copy must not say 'this week' — the page is week-selectable (R-428)."""
    assert "MODEL_WEEK_FLOOR" in SOURCE
    assert not re.search(r"\bthis week\b", SOURCE, re.IGNORECASE), \
        "copy says 'this week' on a page whose week is chosen by the reader"


def test_looking_forward_is_a_stub_that_says_so():
    assert "Looking forward" in SOURCE
    assert "not built yet" in SOURCE, "an empty frame would imply it exists"


def test_the_slate_routes_to_schedule():
    assert "scope.link('schedule')" in SOURCE, "Today must route the slate to Schedule"


def test_a_team_with_no_previous_rank_is_not_rendered_as_no_change():
    """R-431. A blank or a zero reads as 'held station', which is the opposite of the truth."""
    assert "unranked last week" in SOURCE
    assert "pd.isna(row.prev_rank)" in SOURCE


# --- the panels are actually CONSTRUCTIBLE ---------------------------------------------

def test_every_panel_builds_ITS_OWN_columns_and_formats_a_row():
    """EXERCISE THE PAGE'S render path. Do not grep it, and do not rebuild it.

    Two drafts of this test were wrong before this one, and both failures are the same shape.
    The first checked the page's SOURCE for column names, and passed while
    `Col(..., decimals=1)` and `Col(..., fmt=...)` were both wrong — Col takes `dp` and
    `render` — so the page would have tracebacked the first time anyone opened it.
    ci/check_page_queries.py could not see it either: it only executes SQL.

    The second draft constructed its own Col list and asserted that formatted. It passed with
    the bug deliberately reintroduced, because it was testing a list the test wrote rather
    than the one the page writes.

    This one stubs table.render to CAPTURE whatever the page hands it, calls each panel, and
    formats a row through every captured column. If the page builds a Col wrongly, the
    construction raises inside the panel and this fails.
    """
    import sys
    import types

    sys.path.insert(0, str(ROOT / "site"))
    saved_st = sys.modules.get("streamlit")
    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "title", "line_chart"):
        setattr(stub, name, lambda *a, **k: None)
    stub.radio = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else None)
    stub.cache_data = lambda *a, **k: (lambda f: f)
    stub.cache_resource = lambda *a, **k: (lambda f: f)
    sys.modules["streamlit"] = stub
    try:
        from lib import table as table_module
        from views import today as page

        captured = []

        def capture_render(df, columns, *a, **k):
            captured.append(columns)

        def capture_ros(df, view, what, why, renderer=None, **k):
            if renderer is not None and df is not None and not df.empty:
                renderer(df)

        table_module.render = capture_render
        page.table.render = capture_render
        page.states.render_or_state = capture_ros

        row = {"away_team_display": "Away", "home_team_display": "Home",
               "away_points": 21, "home_points": 24, "excitement_index": 8.5,
               "lead_changes": 4, "actual_margin": 3,
               "spread_favorite_side": "home", "moneyline_favorite_side": "home",
               "favorite_definitions_disagree": False,
               "spread_at_close": -3.5, "spread_current": -3.5,
               "market_implied_home_win_probability": 0.62,
               "market_implied_away_win_probability": 0.38}
        games = pd.DataFrame([row])

        class Scope:
            season, week, season_type, conference, division = 2026, 1, "regular", None, "fbs"

            def describe(self):
                return "2026 wk1"

            def link(self, page_name, **k):
                return "#"

        page._most_exciting(games, Scope())
        page._recap_lists(games, Scope())

        assert captured, "no panel handed any columns to table.render"
        sample = pd.Series({**row, "favorite": "Home", "opponent": "Away", "spread": 3.5,
                            "fav_margin": 3, "ats": -0.5, "fav_win_prob": 0.62,
                            "underdog": "Away", "beat": 0.5, "score": "21-24",
                            "matchup": "Away at Home"})
        for columns in captured:
            for col in columns:
                assert isinstance(col.format(sample), str)
    finally:
        if saved_st is not None:
            sys.modules["streamlit"] = saved_st
        else:
            sys.modules.pop("streamlit", None)
