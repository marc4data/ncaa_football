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
    # ⚠️ BOTH DECORATOR FORMS. Streamlit's cache decorators are used bare
    # (`@st.cache_resource` on lib.query.engine) AND called (`@st.cache_data(ttl=300)` on
    # lib.db.freshness). A stub that only handles the called form replaces every BARE-
    # decorated function with `lambda f: f`, so calling it raises
    #     TypeError: <lambda>() missing 1 required positional argument: 'f'
    # which names the stub rather than the thing that broke. Found on 2026-09-09 by running
    # this same stub against the DEPLOYED site container, where the panels reach a real
    # engine() instead of a patched query — the tests never hit it because they stub
    # `page.query`, so the defect was invisible here and only appeared off the laptop.

    def _cache(*a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return lambda f: f

    stub.cache_data = _cache
    stub.cache_resource = _cache
    return stub, calls


# ⚠️ THE PANELS THIS FILE EXERCISES — AND THE REASON IT IS A DECLARED LIST (R-475).
#
# This test calls panels BY NAME. A panel added to today.py and not added here is unguarded
# against the exact defect this file exists for: `Col(..., decimals=1)` construction failures
# that CI cannot see, because check_page_queries only executes SQL and the site-image job
# never calls a panel. The list being silent about a new panel is the fallback-at-100% shape.
#
# So the list is declared here and `test_every_panel_in_the_module_is_exercised` asserts it
# against the module. Adding a panel to today.py without adding it here FAILS rather than
# quietly covering less — which is what the A071 repair was about one layer down.
#
# The values are invokers because the panels do not share a signature: the two recap panels
# are handed a frame the page already fetched, and _movers does its own query so it can count
# what it dropped.
PANELS = {
    "_most_exciting": lambda page, games, scope: page._most_exciting(games, scope),
    "_recap_lists": lambda page, games, scope: page._recap_lists(games, scope),
    "_movers": lambda page, games, scope: page._movers(scope, 10),
    # ⚠️ THESE TWO WERE ALREADY UNEXERCISED WHEN THE GUARD ABOVE WAS WRITTEN (R-475).
    # A074 assumed the exercised set was complete and that only a NEW panel could fall out of
    # it. It was not: _leaderboards builds fifteen Cols across four boards and _bump builds
    # three, and none had ever been called by a test. The guard found them on its first run,
    # which is the argument for deriving the set from the module instead of trusting a list.
    "_leaderboards": lambda page, games, scope: page._leaderboards(scope, 10),
    # R-477. The scatter runs its own query so it can count the teams it dropped, and it
    # needs a scope with a REAL week: under week=None it renders the "pick a week" Empty and
    # would never reach a Col, so exercising it with the page's default scope would have
    # proved nothing — the panel would be in the list and still untested.
    "_profile": lambda page, games, scope: page._profile(scope),
    # Found by widening the discovery above from "renders columns" to "announces itself with
    # a subheader" — a seventh panel that no test had ever called. It is a stub that says
    # Looking forward is not built yet, so there is little to break; it is exercised anyway,
    # because "small" is not a reason to be outside the set and the next edit to it would be
    # unguarded.
    "_looking_forward": lambda page, games, scope: page._looking_forward(scope),
    "_bump": lambda page, games, scope: page._bump(scope),
}


def _panels_defined_in(source: str) -> set:
    """Every module-level panel in today.py, found by what it DOES rather than by its name.

    A panel is a module-level function that ANNOUNCES ITSELF with `st.subheader` — which is
    the actual convention every panel on this page follows. Discovering them from the source
    is what makes the exercised list falsifiable: a naming convention would let a panel opt
    out of coverage simply by being called something else.

    ⚠️ THIS WAS "HANDS COLUMNS TO THE TABLE RENDERER" UNTIL R-477, AND THAT DEFINITION HAD A
    HOLE THE SIZE OF A CHART. A074 defined a panel as a function calling `table.render` or
    `states.render_or_state`. `_profile` draws an inline-SVG scatter through `st.markdown` and
    hands columns to nobody, so the guard written to catch an unexercised panel could not see
    it — it reported `_profile` as a name today.py "no longer defines" while the function sat
    in the file. A guard that is blind to a whole CLASS of panel is the same defect as the
    inert test A071 repaired: it passes, and what it covers is smaller than it looks.

    `st.subheader` is the honest anchor because it is what makes something a panel to a
    READER — a titled block on the page — rather than what it happens to render with.
    """
    import ast

    found = set()
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "subheader"
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == "st"):
                found.add(node.name)
                break
    return found


def _unexercised(exercised) -> set:
    """Panels today.py defines that `exercised` does not call. The guard's whole logic, as a
    function, so a negative test can hand it a deliberately short set and see it complain —
    a guard whose failure path has never run is a guard nobody has tested."""
    return _panels_defined_in(SOURCE) - set(exercised)


def test_the_exercised_set_guard_can_fail():
    """Rule 10. Drop a panel from the set and the guard must name it.

    ⚠️ THE POINT IS THE FAILURE PATH, not the arithmetic. This whole file exists because a
    check that passed while inert was read as evidence for a year of rounds; a coverage guard
    that has only ever been seen passing is the same claim with the same backing.
    """
    assert _unexercised(PANELS) == set(), "precondition: the real set covers the module"
    for dropped in ("_movers", "_leaderboards", "_most_exciting"):
        short = {k: v for k, v in PANELS.items() if k != dropped}
        assert _unexercised(short) == {dropped}, \
            f"dropping {dropped} from the exercised set was not caught"


def test_every_panel_in_the_module_is_exercised():
    """R-475. THE LIST ABOVE MUST COVER THE MODULE, not merely be consistent with itself.

    Without this, adding a panel to today.py silently reduces what the panel-exercise test
    covers, and the suite stays green while covering less — the signature of the A071 defect
    and of B072's self-skipping dag tests. Two greens that mean different things is the thing
    worth preventing.
    """
    defined = _panels_defined_in(SOURCE)
    missing = _unexercised(PANELS)
    assert not missing, (
        f"panels in today.py that no test exercises: {sorted(missing)}. "
        f"Add them to PANELS in this file — a panel nobody calls is a Col nobody builds.")
    stale = set(PANELS) - defined
    assert not stale, f"PANELS names functions today.py no longer defines: {sorted(stale)}"


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
               # ⚠️ R-544. THIS FIXTURE USED TO SAY `"actual_margin": 3` AND CONTRADICTED ITS
               # OWN SCOREBOARD. Home 24, away 21, and the column is AWAY MINUS HOME, so it
               # is -3. The fixture had encoded the home perspective under the away-
               # perspective name — the same confusion as the page bug it failed to catch,
               # which is why exercising the panel against it proved nothing about the sign.
               "lead_changes": 4, "actual_margin": -3,
               "actual_margin_home_perspective": 3,
               "attribution": "cfdb model (fixture)",
               "spread_favorite_side": "home", "moneyline_favorite_side": "home",
               "favorite_definitions_disagree": False,
               "spread_at_close": -3.5, "spread_current": -3.5,
               "market_implied_home_win_probability": 0.62,
               "market_implied_away_win_probability": 0.38,
               # R-475's columns, at the SCALES published serving actually uses: the spread
               # figures are points, and the win-probability ones are already probability
               # POINTS while market_implied_*_win_probability above is a 0-1 fraction. The
               # two do not share a scale and the fixture says so.
               "game_id": 401752817,
               "line_spread_largest_excursion": -6.0,
               "line_spread_move_from_open": -3.0,
               "line_total_largest_excursion": 4.0,
               "line_total_move_from_open": 1.5,
               "line_market_implied_win_probability_largest_excursion": 6.78,
               "line_market_implied_win_probability_move_from_open": 2.10,
               "line_snapshot_count": 94,
               "line_movement_spans_snapshot_gap": True,
               "line_movement_provider_key": "draftkings",
               # What _leaderboards' four boards and _bump's chart read. One frame serves
               # every panel because the query is stubbed once; the panels differ in which
               # columns they reach for, not in where they get them.
               "week": 1, "poll_name": "AP Top 25", "team_display": "Home", "rank": 5,
               "opponent": "Away", "total_yards": 400, "rushing_yards": 150,
               "passing_yards": 250, "player_name": "Player One", "team": "Home",
               "stat_category": "rushing", "stat_value": 120,
               # R-477's columns, at the scales srv_team_week publishes: per-game figures
               # already divided in the view, and games_counted as the denominator they were
               # divided by. games_counted > 0 is what makes the row plottable at all.
               "games_counted": 9,
               "total_yards_for_per_game": 430.5,
               "total_yards_allowed_per_game": 312.25,
               "conference": "Big Ten"}
        games = pd.DataFrame([row])

        class Scope:
            # week is a REAL week, not None: _profile renders a "pick a week" Empty under
            # week=None and would never build a mark, so a None here would put the panel in
            # the exercised set without exercising it.
            season, week, season_type, conference, division = 2026, 1, "regular", None, "fbs"

            def describe(self):
                return "2026 wk1"

            def link(self, page_name, **k):
                return "#"

        # _movers runs its OWN query so it can count the games it dropped, so the query is
        # stubbed rather than the frame handed in. Everything else about it is the real panel.
        page.query = lambda *a, **k: games

        scope = Scope()
        for name, invoke in PANELS.items():
            before_cols, before_calls = len(captured), len(calls)
            invoke(page, games, scope)
            # ⚠️ "PRODUCED OUTPUT", NOT "PRODUCED COLUMNS". _profile draws an SVG scatter and
            # hands columns to nobody, so requiring captured columns would have failed a panel
            # that is working — and, worse, would have pushed the next person to drop chart
            # panels from the exercised set to keep the suite green. A panel earns its place
            # by rendering SOMETHING; the Col-construction check below still applies to
            # whatever columns any of them did build.
            assert len(captured) > before_cols or len(calls) > before_calls, \
                f"panel {name} rendered nothing at all — neither columns nor a streamlit call"

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


# --- R-544: the favourite's margin, and the sign that inverted three panels -------------

# ⚠️ THE FIXTURE IS MARC'S OWN GAME, and the numbers are the real row from published serving
# (game_id 401858211, 2026 week 1), not invented for the test:
#
#     Virginia Tech 73, VMI 3, at home, favoured by 54.5
#     actual_margin                    = away - home = -70   (the convention: AWAY MINUS HOME)
#     actual_margin_home_perspective   = home - away = +70
#
# The favourite is home, so its own margin is +70 and it beat the number by 15.5. The page
# read `actual_margin` for the home branch — the away-perspective column — and reported
# -70 - 54.5 = -124.5, which is what Marc saw on the landing page.
#
# The two branches were each other's: home wants the home-perspective column, and AWAY wants
# `actual_margin`, which already is away-minus-home. Both were exactly backwards, so the sign
# inverted on every graded game rather than on some of them.
VT_VMI = {"actual_margin": -70, "actual_margin_home_perspective": 70,
          "spread_favorite_side": "home", "spread_at_close": -54.5}


def _today():
    """`site/` is not on sys.path at import time; the panel test adds it per-call and undoes
    it. `_favorite_margin` is pure, so this needs neither a stub nor a reload."""
    import sys
    site_path = str(ROOT / "site")
    if site_path not in sys.path:
        sys.path.insert(0, site_path)
    from views import today
    return today


def _row(**over):
    import pandas as pd
    base = dict(VT_VMI)
    base.update(over)
    return pd.Series(base)


def test_the_favourites_margin_is_its_own_margin_not_the_away_perspective():
    """Marc's game: favoured by 54.5, won by 70, therefore +15.5 against the number."""
    today = _today()

    row = _row()
    margin = today._favorite_margin(row)
    assert margin == 70, (
        f"the favourite won by 70; the page computed {margin}. `actual_margin` is AWAY minus "
        f"home, so a HOME favourite's margin is actual_margin_home_perspective.")
    ats = margin - abs(row.spread_at_close)
    assert ats == 15.5, f"expected +15.5 against the spread, got {ats}"


def test_an_away_favourite_reads_the_away_perspective_column():
    """The mirror branch. `actual_margin` IS away-minus-home, so an away favourite takes it."""
    today = _today()

    # Away team wins 30-10: actual_margin = away - home = +20.
    row = _row(actual_margin=20, actual_margin_home_perspective=-20,
               spread_favorite_side="away", spread_at_close=7.0)
    assert today._favorite_margin(row) == 20


def test_favorites_that_lost_outright_contains_only_favorites_that_lost():
    """R-544's third panel: its caption and its contents said opposite things.

    `lost = graded[graded["fav_margin"] < 0]` under the inverted sign selected favourites who
    WON. Measured on 2026 week 1 before the fix: 0 of 10 rows held a favourite that lost —
    the top row was Navy, a 30.5-point favourite that won by 27.
    """
    import pandas as pd
    today = _today()

    # ⚠️ TAGGED BY NAME, NOT BY THE NUMBER UNDER TEST. The first draft of this test asserted
    # on `fav_margin` values and PASSED against the inverted code, because under the bug the
    # winner's margin is -70 and "is -70 negative" is true for the wrong reason. A selection
    # test has to identify the rows it expected by something the bug cannot move.
    frame = pd.DataFrame([
        # A favourite that WON big — must never appear in "lost outright".
        dict(VT_VMI, tag="won_by_70"),
        # A genuine upset: home favoured by 29, lost by 16.
        {"actual_margin": 16, "actual_margin_home_perspective": -16,
         "spread_favorite_side": "home", "spread_at_close": -29.0, "tag": "lost_by_16"},
    ])
    frame["fav_margin"] = frame.apply(today._favorite_margin, axis=1)
    lost = frame[frame["fav_margin"] < 0]

    assert set(lost["tag"]) == {"lost_by_16"}, (
        f"'favorites that lost outright' selected {sorted(lost['tag'])}. Measured on 2026 "
        f"week 1 before the fix: 0 of 10 rows held a favourite that lost.")
