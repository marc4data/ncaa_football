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

# ⚠️ THE MODULES THAT MUST BE RELOADED, AND WHY THIS TUPLE EXISTS (R-447).
#
# Every module here holds its own `import streamlit as st`, so it binds whatever streamlit
# was in sys.modules AT ITS FIRST IMPORT and never looks again. Swapping sys.modules is
# therefore a no-op against an already-imported module — and tests/test_site_foundation.py
# imports every view module in the registry against the REAL streamlit, and sorts BEFORE
# this file. Session B measured it (B069, R-447): in a full run this test's stub reached
# neither views.today nor lib.states, and the test passed anyway because the capture works
# by explicit attribute patching, which is independent of the stub.
#
# Order matters: dependencies before views.today, so the page re-imports the reloaded ones.
# This is the mechanism tests/test_matchup_drives.py and tests/test_view_columns.py already
# use. It is deliberately the same one — a third approach would be a third thing to get
# wrong.
_RELOAD = ("lib.query", "lib.table", "lib.states", "lib.attribution", "lib.filters",
           "lib.shell", "views.today")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


def _stub_streamlit():
    """A stub that RECORDS what reached it, so an assertion can depend on being bound.

    The recording is the point. A stub of no-op lambdas cannot be distinguished from real
    streamlit tolerating the same calls headlessly, which is exactly how the inert version
    of this test passed for a round. `calls` is empty if the page is talking to the real
    module, and the test requires the page's own headings to be in it.
    """
    import types

    calls = []
    stub = types.ModuleType("streamlit")

    def _record(name):
        def fn(*a, **k):
            calls.append((name, a[0] if a else None))
            return None
        return fn

    for name in ("subheader", "caption", "markdown", "write", "title", "line_chart",
                 "dataframe", "columns", "container", "info", "warning", "error"):
        setattr(stub, name, _record(name))
    # Returns the FIRST option so a branch is taken rather than skipped. Under real
    # streamlit this returns whatever the widget state holds, which is why a run against
    # the real module is not the same test.
    stub.radio = lambda *a, **k: (calls.append(("radio", a[0] if a else None))
                                  or (a[1][0] if len(a) > 1 and a[1] else None))
    stub.cache_data = lambda *a, **k: (lambda f: f)
    stub.cache_resource = lambda *a, **k: (lambda f: f)
    return stub, calls


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

    ⚠️ THE THIRD DRAFT — this test as it shipped in A067 — was INERT in a full run, and
    passed while inert. It swapped sys.modules["streamlit"] but never reloaded the modules
    that had already bound the real one. See _RELOAD above. The repair (R-447) reloads them,
    puts them back, and — because a pass is not a proof for a test that passed while inert —
    makes the assertion DEPEND on the stub: the stub records, and the page's own headings
    must be in that recording. Against real streamlit `calls` is empty and this test fails
    rather than passing quietly.

    This one stubs table.render to CAPTURE whatever the page hands it, calls each panel, and
    formats a row through every captured column. If the page builds a Col wrongly, the
    construction raises inside the panel and this fails.
    """
    import sys

    # ⚠️ BOTH of these are undone in the finally, and the pre-repair version undid neither
    # the sys.path entry nor the module bindings. A test file that leaves the stub bound
    # breaks other test files: B066's first draft failed six tests in test_site_foundation
    # and test_scores_page that way. monkeypatch cannot do this either — its sys.modules
    # undo runs AFTER fixture teardown — so the swap and the restore are both by hand.
    site_path = str(ROOT / "site")
    path_added = site_path not in sys.path
    if path_added:
        sys.path.insert(0, site_path)
    saved_st = sys.modules.get("streamlit")
    stub, calls = _stub_streamlit()
    sys.modules["streamlit"] = stub
    try:
        _reload_all()
        page = sys.modules["views.today"]
        table_module = sys.modules["lib.table"]

        # The stub is bound only if the reload above actually happened. Assert it here
        # rather than trusting it, because this is the exact thing that was silently false.
        assert page.st is stub, "views.today is not talking to the stub — the reload failed"
        assert sys.modules["lib.states"].st is stub, "lib.states is not talking to the stub"

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

        # ⚠️ THE ASSERTION THAT DEPENDS ON THE STUB. Under real streamlit these calls go
        # somewhere else and `calls` is empty, so this fails instead of passing quietly —
        # which is the whole difference between this version and the inert one.
        headings = [arg for name, arg in calls if name == "subheader"]
        assert "Most exciting" in headings, \
            f"_most_exciting's heading never reached the stub; recorded: {headings}"
        assert "How the week went against the market" in headings, \
            f"_recap_lists' heading never reached the stub; recorded: {headings}"

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
        _reload_all()
        if path_added and site_path in sys.path:
            sys.path.remove(site_path)
