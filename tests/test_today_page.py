"""Looking Back — the page's own guarantees (R-428 … R-431).

The page reads four serving views and does no arithmetic on the numbers it ranks. These tests
pin the two things that would be silently wrong rather than loud: the grain under a summing
leaderboard, and the poll delta for a team with no previous rank.
"""
import pytest
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
    "_profile": lambda page, games, scope: page._profile(scope, 10),
    # Found by widening the discovery above from "renders columns" to "announces itself with
    # a subheader" — a seventh panel that no test had ever called. It is a stub that says
    # Looking forward is not built yet, so there is little to break; it is exercised anyway,
    # because "small" is not a reason to be outside the set and the next edit to it would be
    # unguarded.
    "_looking_forward": lambda page, games, scope: page._looking_forward(scope, 10),
    "_bump": lambda page, games, scope: page._bump(scope, 10),
    # ⚠️ R-573 ADDED THIS ONE, AND `_panels_defined_in` CANNOT SEE IT. That helper discovers
    # panels by `st.subheader`, which is the convention every other panel follows; `_recap`
    # announces nothing of its own because the two panels it wraps carry their own
    # subheaders. So the coverage guard would NOT have failed when this was extracted out of
    # body() by R-573, and the panel would have sat in TABS untested. Listed by hand for
    # exactly that reason — the discovery rule is good and this is the case it does not
    # cover, which is worth a line rather than a widening of the rule.
    "_recap": lambda page, games, scope: page._recap(scope, 10),
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

    ⚠️ R-573 FOUND THE SECOND HOLE, AND IT IS THE SAME SHAPE AS R-477's. The subheader rule
    misses a panel that announces nothing of its own: `_recap` wraps `_most_exciting` and
    `_recap_lists`, which carry their own subheaders, so it has none. It was extracted out of
    body() so TABS could name it, and under the subheader rule alone this guard would have
    reported it as a function today.py "no longer defines" — the identical symptom `_profile`
    produced — while it sat in the file and on a tab.

    So a panel is EITHER of two things now, and the union is deliberate:

      it announces itself   `st.subheader`, the reader's definition
      body() calls it       a module-level `(scope, depth) -> None`, which is the signature
                            TABS resolves and invokes, and which excludes the query helpers:
                            `_team_yardage(scope, depth)` takes the same two arguments and
                            returns a DataFrame, which is why the annotation is part of the
                            rule rather than decoration.

    ⚠️ Neither rule is a naming convention, so a panel still cannot opt out of coverage by
    being called something else — which is the property R-475 built this for.
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
        args = [a.arg for a in node.args.args]
        returns_none = isinstance(node.returns, ast.Constant) and node.returns.value is None
        if args == ["scope", "depth"] and returns_none:
            found.add(node.name)
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
               # A118. Most Exciting's own columns. ⚠️ THE FIXTURE CARRIES A GAME THAT WENT
               # TO OVERTIME, deliberately: a 4-period row would exercise the scoreboard's
               # easy branch only, and the overtime branch is the one carrying A117's lesson
               # that overtime must never be folded into the fourth quarter.
               # (`game_id`, which the ESPN link reads, is already set further down.)
               "lead_changes_fourth_quarter": 6, "lead_changes_overtime": 3,
               # A153: the panel ranks, filters and displays on these now. They sit BESIDE the
               # win-probability counts rather than replacing them, because the page still
               # selects both and a fixture that dropped the old ones would stop covering the
               # aliases `test_the_page_reads_the_corrected_columns` pins.
               "scoreboard_lead_changes_fourth_quarter": 2,
               "scoreboard_lead_changes_overtime": 1, "scoreboard_lead_changes": 3,
               "largest_single_play_swing_fourth_quarter": 0.425,
               "home_win_probability_range_fourth_quarter": 0.60,
               "plays_with_win_probability_fourth_quarter": 39,
               "mean_distance_from_even_fourth_quarter_onward": 0.222,
               "home_periods": 5, "away_periods": 5,
               "home_q1": 7, "home_q2": 3, "home_q3": 3, "home_q4": 10,
               "away_q1": 7, "away_q2": 10, "away_q3": 3, "away_q4": 3,
               "home_overtime_points": 13, "away_overtime_points": 15,
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
               # A122. The curve cell reads `game_id`, to slice the batched frame.
               #
               # ⚠️ AND THE CURVE'S OWN COLUMNS, because `page.query` is stubbed ONCE and every
               # panel gets this same frame — including `_win_probability_curves`. Without them
               # the sparkline raises KeyError inside the cell renderer, which is this test
               # working: it exercises the real render path rather than a list it wrote itself.
               "season": 2026,
               "play_number": 1, "period": 1, "is_overtime": False,
               "home_win_probability": 0.62,
               # A138. THE CHART'S X AXIS IS THE CLOCK NOW, not `play_number` —
               # cfdb-main-R-916 measured that column non-chronological on 336 of 1,898 games.
               "elapsed_from_kickoff_seconds": 120,
               "overtime_period": None, "overtime_axis_offset_periods": None,
               # A138. The truncation flag the chart reads to decide whether it may print a
               # final value at all.
               "win_probability_curve_reaches_final_score": True,
               # A139, cfdb-main-R-934. `_completed_games` selects this now, so the panel
               # fixture carries it: the curve's final value names the HOME side on screen.
               "home_abbreviation": "HOME", "away_abbreviation": "AWAY",
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


def _winprob():
    """The win-probability curve, promoted to `lib/` by A170 so Matchup can draw it too.

    Same sys.path dance as `_today()` and for the same reason. The chart's tests live here
    rather than moving with it: they assert what TODAY's panel renders, and that is still
    the thing Marc is looking at.
    """
    import sys
    site_path = str(ROOT / "site")
    if site_path not in sys.path:
        sys.path.insert(0, site_path)
    from lib import winprob
    return winprob


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


# --- the quarter scoreboard, and the two absences it must not confuse -------------------

def _scoreline(**over):
    """One srv_game row's worth of scoreboard columns, as a Series."""
    import pandas as pd
    base = {"home_periods": 4, "away_periods": 4,
            "home_q1": 7, "home_q2": 3, "home_q3": 0, "home_q4": 7,
            "away_q1": 0, "away_q2": 10, "away_q3": 3, "away_q4": 0,
            "home_overtime_points": None, "away_overtime_points": None}
    base.update(over)
    return pd.Series(base)


def test_a_scoreless_quarter_is_a_zero_and_an_unplayed_one_is_absent():
    """🚨 AC-G.32, and the two cases are one character apart in the output.

    A line reading `7 · 0 · 3 · 0` says the team was shut out in two quarters — a fact about
    the game. A line reading `7 · 0 · 3` says the game had three quarters, which happens to no
    completed game. So printing a fixed four values and filling the gaps with zeroes would
    invent shut-out quarters, and printing only the non-zero ones would delete real ones.

    Both directions are asserted, because a fix for either one alone produces the other.

    ⚠️ A138 MOVED THIS ONTO `_quarter_cells`. The states are unchanged; only their container is.
    """
    today = _today()
    played = today._quarter_cells(_scoreline(), "home")
    assert played == [("1", "7"), ("2", "3"), ("3", "0"), ("4", "7")], (
        f"a played, scoreless quarter must render 0, got {played!r}")

    # A game whose feed carries only three periods must not grow a fourth.
    short = today._quarter_cells(_scoreline(home_periods=3, home_q4=None), "home")
    assert short == [("1", "7"), ("2", "3"), ("3", "0")], (
        f"an unplayed quarter must be absent, not zero — got {short!r}")


def test_overtime_is_labelled_and_never_folded_into_the_fourth_quarter():
    """🚨 A117's lesson, applied to the display rather than to the model.

    Jacksonville State @ Ohio had 19 lead changes: TWO in the fourth quarter and ELEVEN in
    overtime. A scoreboard that added overtime points onto Q4 would tell a reader the drama
    happened in a quarter where it did not — and every number on the line would still be a
    real number, which is what makes it worth a test rather than a comment.
    """
    today = _today()
    pairs = today._quarter_cells(_scoreline(home_periods=5, home_overtime_points=13), "home")

    assert len(pairs) == 5, f"a 5-period game shows five columns, got {pairs}"
    assert pairs[:4] == [("1", "7"), ("2", "3"), ("3", "0"), ("4", "7")], \
        "the four quarters are unchanged by overtime"
    assert pairs[4] == ("OT", "13"), f"overtime must be LABELLED, got {pairs[4]!r}"
    assert pairs[3][1] != "20", "overtime points must not be added onto the fourth quarter"


def test_the_overtime_label_cannot_be_broken_across_two_lines():
    """⚠️ A REAL DEFECT THIS PANEL SHIPPED AND THEN FIXED, AND A138 MADE IT STRUCTURAL.

    The joined version rendered `7 · 10 · 3 · 3 · O` / `T 15` at Wake Forest at Purdue — the
    wrap landed INSIDE the word "OT", because `&nbsp;&middot;&nbsp;` had made the whole line one
    unbreakable run with nowhere legal to break.

    ✅ In the grid each value is its own `<td>`, so there is no run to break at all. The
    assertion is therefore about the STRUCTURE rather than about the separators: the label and
    its number are in different cells, and no cell holds a joined line.
    """
    today = _today()
    html = today._scoreboard(_scoreline(home_periods=5, away_periods=5,
                                        home_overtime_points=15, away_overtime_points=7))
    assert ">OT</th>" in html, "the label is a column header, not part of a value"
    assert "&middot;" not in html, (
        "no cell may hold a joined run — that is the shape that wrapped mid-word")
    assert ">15</td>" in html, "and the overtime number is a cell of its own"


def test_a_game_with_no_period_data_reads_as_a_dash():
    """An absence that says which absence it is: no periods means no scoreboard, not 0-0-0-0.

    🚨 AND IN THE GRID THE WHOLE LINE HAS TO BE EM DASHES, NOT BLANKS. A blank cell already
    means "that side has no such period"; using it for "we do not have the number" is the exact
    collapse `_quarter_cells` exists to prevent, and a grid is where it is easiest to commit.
    """
    today = _today()
    assert today._quarter_cells(_scoreline(home_periods=None), "home") is None

    # ⚠️ THE FINAL SCORE IS GIVEN, so the em dashes counted below are the QUARTERS only — a
    # fixture with no points would put a fifth em dash in the final column and the assertion
    # would pass for the wrong reason.
    html = today._scoreboard(_scoreline(home_periods=None, home_points=24, away_points=23))
    home = html[html.index("cfdb-sb-home"):]
    assert home.count(">\u2014</td>") == 4, (
        "a side with no period count reads as four em dashes, not four blanks")
    assert ">24</td>" in home, "and its final score is still a number"


# --- the ESPN link ----------------------------------------------------------------------

def test_the_espn_link_uses_the_game_id_and_leaves_the_site_visibly():
    """✅ THE KEY WAS VERIFIED BY HAND ON THREE GAMES BEFORE THIS SHIPPED.

    CFBD's game_id being ESPN's event id is widely believed and had never been established
    here. A wrong id does not fail — it serves a DIFFERENT GAME, which is worse than no link.
    Checked against ESPN's own summary endpoint: 401856679 -> Oklahoma 10 at Michigan 17,
    401856682 -> Ohio State 23 at Texas 24, 401866418 -> Jacksonville State 27 at Ohio 29.
    Teams, sides and final scores all matched, and all three gamecast URLs returned HTTP 200.

    ⚠️ EXTERNAL, AND IT MUST READ AS EXTERNAL — a reader should know before they click that
    they are leaving. `rel` is asserted too: a new tab opened from our page would otherwise
    hold a handle back to it.
    """
    import pandas as pd
    today = _today()
    html = today._espn_link(pd.Series({"game_id": 401856679}))

    assert "gameId/401856679" in html, f"the link must carry the game id, got {html!r}"
    assert 'target="_blank"' in html or "target='_blank'" in html, "external links open away"
    assert "noopener" in html and "noreferrer" in html, "a new tab must not keep a handle back"
    assert "&nearr;" in html or "↗" in html, "the reader should see that it leaves the site"


def test_a_row_with_no_game_id_gets_no_link_rather_than_a_broken_one():
    """A link to gameId/None is a 404 dressed as a feature."""
    import pandas as pd
    today = _today()
    assert today._espn_link(pd.Series({"game_id": None})) == "—"


# --- the ordering decision lives in exactly one place ------------------------------------

def test_most_exciting_orders_on_published_columns_and_does_no_arithmetic():
    """🚨 §4.2, and R-709's whole point: the page must not compute the ranking.

    Marc asked for a ranking that reflects fourth-quarter drama. The temptation is a weighted
    score in the page; A114, A115 and A117 all refused to build one and so does this. The
    ordering is an `order by` on two PUBLISHED columns with an explicit tie-break, held in a
    single named constant so changing what "most exciting" means is one line.
    """
    assert "MOST_EXCITING_ORDER" in SOURCE, "the ordering decision must be named, not inline"
    order = re.search(r'MOST_EXCITING_ORDER = \((.*?)\)\n', SOURCE, re.S).group(1)
    # ⚠️ A140 POINTED THE SAME KEY AT THE CORRECTED COLUMN (cfdb-main-R-916). The weighting is
    # unchanged — same two keys, same directions, same tie-break — and the assertion below is the
    # one that would catch a key being added or removed, which IS Marc's call.
    # ✅ A153, §3.3's MIGRATE: the first key is now the SCOREBOARD's own lead changes — Marc's
    # call, with A152's numbers in front of him. **A140's property survives and is asserted
    # separately below**: whatever the key is, it must never be a column built on the FEED's
    # ordering, which is non-chronological on 336 of 1,898 games.
    assert "scoreboard_lead_changes_fourth_quarter desc" in order, (
        "the first key must be the scoreboard lead-change count — the number the panel's own "
        "caption promises")
    # 🚨 THE GUARD A140 LEFT AND A153 KEEPS. `scoreboard_lead_changes_fourth_quarter` is computed
    # on the clock ordering in the mart, so pointing the key at a bare feed-ordered column would
    # be a silent regression to exactly what cfdb-main-R-916 measured.
    #
    # ⚠️ THE BOUNDARY IS LOAD-BEARING AND THE FIRST DRAFT OF THIS LOOP DID NOT HAVE ONE:
    # `"scoreboard_lead_changes_fourth_quarter desc"` CONTAINS `"lead_changes_fourth_quarter
    # desc"`, so a plain `not in` failed on the very key it was meant to bless. `\b` after a
    # non-word boundary is what separates a column name from a longer one that ends with it.
    for feed_ordered in ("lead_changes_fourth_quarter", "lead_changes",
                         "largest_single_play_swing"):
        assert not re.search(rf"(?<![a-z_]){feed_ordered} desc", order), (
            f"{feed_ordered!r} orders on the feed's play_number, which is non-chronological on "
            f"336 of 1,898 games")
    assert order.count(",") == 2, (
        "two keys and a tie-break, as before — adding or removing one is a weighting change and "
        "is Marc's, not a round's")
    assert "mean_distance_from_even_fourth_quarter_onward asc" in order, (
        "the tie-break must be explicit — fourth-quarter lead changes is a small integer and "
        "ties are the common case, so without it the order inside a tie is planner accident")
    assert order.count("nulls last") >= 2, (
        "a game whose feed never reached the fourth quarter must not sort as a dull one")
    assert "order by {MOST_EXCITING_ORDER}" in SOURCE, "the query must use the named constant"
    # No weighting, no scaling, no composite — the line this project has held three times.
    for banned in ("* 0.", "weight", "z_score", "normali"):
        assert banned not in order, f"no composite index: found {banned!r} in the ordering"


# --- the win-probability curve ----------------------------------------------------------

def _curve(n=40, overtime_from=None):
    """A game's worth of plotted points, in clock order.

    🚨 A138. THE FIXTURE CARRIES THE CLOCK COORDINATES, and the two are mutually exclusive
    exactly as the warehouse publishes them: `elapsed_from_kickoff_seconds` is NULL for every
    overtime play and `overtime_axis_offset_periods` is NULL in regulation. A fixture where
    both were populated could not test the thing the columns exist to keep apart.
    """
    import pandas as pd
    regulation = n if overtime_from is None else overtime_from
    overtime_plays = 0 if overtime_from is None else n - overtime_from
    rows = []
    for i in range(n):
        in_overtime = overtime_from is not None and i >= overtime_from
        rows.append({
            "game_id": 1, "play_number": i,
            "period": 1 + i // 10 if not in_overtime else 5,
            "is_overtime": None if overtime_from is None else in_overtime,
            "elapsed_from_kickoff_seconds":
                None if in_overtime else round(i / max(regulation - 1, 1) * 3600),
            "overtime_period": 1 if in_overtime else None,
            "overtime_axis_offset_periods":
                ((i - overtime_from) / max(overtime_plays, 1)) if in_overtime else None,
            "home_win_probability": 0.5 + 0.4 * ((i % 7) - 3) / 3,
            "home_score": i, "away_score": i, "play_text": "a play",
        })
    frame = pd.DataFrame(rows)
    # ⚠️ OBJECT DTYPE ON PURPOSE, AND R-744 IS WHY. Built from bools, pandas types this column
    # `bool` and then REFUSES to store a null in it — `LossySetitemError`. The live column is
    # nullable (the one play of 291,548 with no stg_play match), so a fixture that cannot hold a
    # null is a fixture that cannot test the case the column exists to handle.
    frame["is_overtime"] = frame["is_overtime"].astype("object")
    return frame


def _polyline_xs(svg: str):
    """Every polyline's x coordinates, in the order they are plotted."""
    xs = []
    for points in re.findall(r"<polyline points='([^']*)'", svg):
        xs.extend(float(p.split(",")[0]) for p in points.split())
    return xs


def test_the_curve_is_plotted_in_clock_order_and_the_assertion_can_actually_fire():
    """🚨 R-760's QUESTION, ASKED OF THIS TEST BEFORE IT WAS WRITTEN: what would have to be
    wrong for it to fire?

    ⚠️ A121's guard could not answer that. It asserted a `row_number()` column was monotonic —
    monotonic BY CONSTRUCTION — so it fired on 0 rows under the very break it was written for.

    This one fires when the points arrive in any order but play order, which is exactly what
    changing one clause in `_win_probability_curves` produces: `order by game_id,
    home_win_probability` instead of `order by game_id, play_number`. Every point is real, the
    count is right, and the line becomes a smooth ramp — which looks like a SMOOTHED curve, so
    it does not read as broken to anyone glancing at it.

    ✅ SO THE SECOND HALF IS THE PROOF: the same frame, sorted the way the break would sort it,
    must make the assertion FAIL. A guard that cannot be shown failing is decoration.
    """
    winprob = _winprob()

    ordered = _curve()
    xs = _polyline_xs(winprob.sparkline_svg(ordered))
    assert xs == sorted(xs), "a frame in play order must plot left to right"

    # The break, reproduced: same points, ordered by probability.
    scrambled = ordered.sort_values("home_win_probability").reset_index(drop=True)
    broken_xs = _polyline_xs(winprob.sparkline_svg(scrambled))
    assert broken_xs != sorted(broken_xs), (
        "the assertion above cannot fail, so it proves nothing — a frame ordered by probability "
        "must plot out of order")


def test_the_curve_query_orders_by_the_clock_and_not_by_play_number():
    """🚨 cfdb-main-R-916. `play_number` IS NOT CHRONOLOGICAL AND THE CHART USED TO TRUST IT.

    Measured on the published curve: **795 consecutive pairs step BACKWARDS on the clock, across
    336 of 1,898 games (17.7%)**, worst single back-step −3,567 seconds. Game 401635615 carries
    fourth-quarter plays at `play_number` 0–3 and a first-quarter play at 4.

    ⚠️ `nulls last` IS LOAD-BEARING AND IS ASSERTED SEPARATELY. `elapsed_from_kickoff_seconds`
    is NULL for every overtime play by design, so without it the sort puts overtime at the FRONT
    of the game — R-890's shape, and the symptom would be a line that starts in overtime.

    ✅ `play_number` SURVIVES AS THE TIE-BREAK, which is the one place it is still right: inside
    an overtime period it is the only order a play has.
    """
    assert "order by game_id, elapsed_from_kickoff_seconds nulls last, play_number" in SOURCE, (
        "the curve query must order by the clock, with nulls last, and use play_number only as "
        "the tie-break inside overtime")
    assert "order by game_id, play_number\n" not in SOURCE, (
        "the old play_number ordering must be gone, not merely joined")


def test_overtime_breaks_the_line_and_regulation_does_not():
    """🚨 A118's RULE, APPLIED TO A CURVE: overtime must never read as a longer fourth quarter.

    Jacksonville State at Ohio had TWO fourth-quarter lead changes and ELEVEN in overtime. On an
    unmarked curve that attributes the drama to the wrong part of the game with every point
    still real.

    ⚠️ AND THE SHADING ALONE COULD NOT CARRY IT — A122 rasterised it and looked. `play_number`
    COMPRESSES overtime into a sliver: Wake Forest at Purdue's 24 overtime plays of 171 are 20
    pixels at the right-hand edge. The break is what survives that, so the break is what is
    asserted.
    """
    winprob = _winprob()
    assert winprob.sparkline_svg(_curve()).count("<polyline") == 1, \
        "a game with no overtime is one continuous line"
    assert winprob.sparkline_svg(_curve(overtime_from=30)).count("<polyline") == 2, \
        "overtime must be a separate segment, not a continuation"


def test_an_unknown_period_is_never_read_as_regulation():
    """⚠️ AC-G.32, and the live data contains this case: `is_overtime` is NULL — not False — on
    the one play of 291,548 with no `stg_play` match.

    Read as regulation it would draw a break that did not happen; read as overtime it would
    suppress a real one. `is True` does neither.
    """
    winprob = _winprob()
    import pandas as pd
    frame = _curve(overtime_from=30)
    frame.loc[frame["play_number"] == 29, "is_overtime"] = None
    svg = winprob.sparkline_svg(frame)
    assert svg.count("<polyline") == 2, "a null play must not add or remove a break"
    assert pd.isna(frame.loc[frame["play_number"] == 29, "is_overtime"]).all()


def test_the_curve_is_never_smoothed():
    """❌ NO SMOOTHING, NO INTERPOLATION, NO ROLLING AVERAGE — every published point is plotted.

    The spikes ARE the drama and this panel exists to show them; a smoothed win-probability
    curve is a different claim about the game and a reader cannot tell the two apart.
    """
    winprob = _winprob()
    frame = _curve(n=40)
    plotted = _polyline_xs(winprob.sparkline_svg(frame))
    assert len(plotted) == 40, (
        f"{len(plotted)} points plotted from a 40-play frame — something is resampling")


# --- A138: the clock axis, the fill, the label and the scoreboard -------------------------

def test_the_chart_positions_on_the_clock_and_not_on_play_number():
    """🚨 cfdb-main-R-916, AND THIS IS THE TEST THE OLD SUITE COULD NOT HAVE WRITTEN.

    The published feed's `play_number` is not chronological on 336 of 1,898 games. Game
    401635615 is the shape reproduced here: its `play_number` 0–3 are FOURTH-QUARTER plays at
    3,528–3,590 seconds and `play_number` 4 is a first-quarter play at 23 seconds. Drawn on
    `play_number` the line crosses the whole width backwards with every point real.

    ⚠️ THE OLD ORDER-TEST COULD NOT SEE THIS because its fixture had the two axes agreeing —
    which is R-744's family: a fixture whose defaults make the assertion true. This one builds
    a frame where they DISAGREE, so it fires on exactly the defect that shipped.
    """
    winprob = _winprob()
    import pandas as pd
    rows = []
    # Four fourth-quarter plays first by play_number, then the rest of the game.
    for play_number, elapsed in enumerate([3528, 3534, 3584, 3590]):
        rows.append({"game_id": 1, "play_number": play_number, "period": 4,
                     "is_overtime": False, "elapsed_from_kickoff_seconds": elapsed,
                     "overtime_period": None, "overtime_axis_offset_periods": None,
                     "home_win_probability": 0.5})
    for index, elapsed in enumerate([23, 58, 87, 109]):
        rows.append({"game_id": 1, "play_number": 4 + index, "period": 1,
                     "is_overtime": False, "elapsed_from_kickoff_seconds": elapsed,
                     "overtime_period": None, "overtime_axis_offset_periods": None,
                     "home_win_probability": 0.5})
    frame = pd.DataFrame(rows)
    frame["is_overtime"] = frame["is_overtime"].astype("object")

    # The page receives the frame in the order the SQL returns it — by the clock.
    in_clock_order = frame.sort_values("elapsed_from_kickoff_seconds").reset_index(drop=True)
    xs = _polyline_xs(winprob.sparkline_svg(in_clock_order))
    assert xs == sorted(xs), "a frame in clock order must plot left to right"

    # ✅ AND THE PROOF THAT IT CAN FAIL: the same points in `play_number` order — which is what
    # the old query returned — must NOT plot left to right.
    by_play_number = frame.sort_values("play_number").reset_index(drop=True)
    broken = _polyline_xs(winprob.sparkline_svg(by_play_number))
    assert broken != sorted(broken), (
        "play_number order must plot backwards on this frame, or the assertion above proves "
        "nothing about which axis the chart uses")


def test_the_curve_is_filled_from_zero_and_the_zero_is_the_middle():
    """Marc: "Make it an area chart … -1 to 1". Fill from zero makes the SIGN the picture.

    ⚠️ AC-G.22: above-or-below the line is POSITION and survives greyscale; the fill is
    decoration on a signal that already works without it. So the assertion is that the filled
    path STARTS AND ENDS on the zero line — an area hung off the top or the bottom of the box
    would still look like an area chart and would say something else entirely.
    """
    winprob = _winprob()
    svg = winprob.sparkline_svg(_curve())
    paths = re.findall(r"<path d='([^']*)'", svg)
    assert paths, "an area chart has a filled path"
    for d in paths:
        first = d.split()[0]                       # M x,y
        last = [p for p in d.split() if p.startswith("L")][-1]
        start_y = float(first.split(",")[1])
        end_y = float(last.split(",")[1])
        assert abs(start_y - end_y) < 0.05, (
            "the fill must close on one horizontal baseline, not on the curve")
    assert "<polyline" in svg, "the line survives the fill — the spikes are the drama"


def _svg_label(svg: str) -> str:
    """The sparkline's end label as a READER sees it, tags stripped.

    🚨 A167 SPLIT THE LABEL INTO TWO `tspan`s so the percentage could be bigger and blue — Marc:
    *"Increase the font of the final win % and make it blue to help it pop out."* ⚠️ **Three
    tests in this file asserted `"%</text>"` or `f">{text}</text>"`, which describe the MARKUP
    and not the label.** The rendered text never changed; the assertions were reading the wrong
    thing, and this is what they read now.
    """
    import re
    # ⚠️ THE LEADING `.*` IS LOAD-BEARING: A167 also added `<text>` marks for the quarter
    # labels, so a non-greedy match from the FIRST one swallows `1Q2Q3Q4Q` into the answer. The
    # end label is the LAST text mark in the SVG.
    match = re.search(r".*<text\b[^>]*>(.*?)</text>\s*</svg>", svg, re.S)
    return re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""


def test_a_truncated_curve_is_never_labelled_with_a_final_value():
    """🚨 AC-G.11, AND IT IS ONE ROW IN NINE RATHER THAN A DEFENSIVE BRANCH.

    99 of 1,898 published curves never reach their own game's final score (A136). A138 measured
    what a reader actually meets: **38 of 337 top-ten rows across 35 season-weeks, in 22 of those
    weeks, two of them at #1.** Coastal Carolina at UTSA ends at 0.1% for a side that won 44-15.

    Printing "0%" beside that line is a confident wrong number a reader cannot tell from a real
    collapse — so the label is withheld and the end of the line is cut and named instead.
    """
    winprob = _winprob()
    import pandas as pd
    points = _curve()
    row = pd.Series({"win_probability_curve_reaches_final_score": True,
                     "home_abbreviation": "MICH"})
    cut_row = pd.Series({"win_probability_curve_reaches_final_score": False,
                         "home_abbreviation": "MICH"})

    # ⚠️ A139 MOVED THE DECISION INTO `_curve_label`, so the label is built ONCE per row and
    # handed to the renderer. Exercising it through that function is exercising what ships.
    text, is_cut = winprob.curve_label(row, points)
    cut_text, cut_is_cut = winprob.curve_label(cut_row, points)
    complete = winprob.sparkline_svg(points, label=text, is_cut=is_cut)
    truncated = winprob.sparkline_svg(points, label=cut_text, is_cut=cut_is_cut)

    assert _svg_label(complete).endswith("%"), (
        "a complete curve labels its final value — Marc asked for it")
    assert not _svg_label(truncated).endswith("%"), (
        "a truncated curve must not print a final value: the number is not one")
    assert "cut</text>" in truncated, "the absence has to say which absence it is"
    assert "stroke-dasharray='1 2'" in truncated, "and be visible without reading the label"
    assert "feed stops" in truncated, "including to a screen reader"
    assert "feed stops" not in complete
    # 🚨 cfdb-main-R-934: AND THE COMPLETE ONE NAMES ITS SIDE, on screen and not only in the
    # accessible label. A bare percentage beside a scoreboard whose TOP line is the away team
    # reads as the away team's number.
    assert "MICH" in complete, "the visible label must name the home side"
    assert "home side" in complete, "and the aria-label must not say less than the pixels"
    assert "MICH" not in truncated, "the cut case has no value to attribute to anybody"


def test_overtime_is_wider_and_the_scale_is_shared():
    """✅ READING B — shared SCALE, not shared extent. Marc asked for both "consistent across
    all rows" and "games with overtime will be longer", and only this reading gives both.

    📊 A136 measured the alternative: sizing every chart to the week's longest game spends
    15.8-42.9% of a regulation chart's width on emptiness. The assertion here is the property
    that makes reading B true — a quarter boundary lands at the SAME pixel on both charts, and
    the overtime one is longer because it contains more game.
    """
    winprob = _winprob()
    regulation = winprob.sparkline_svg(_curve())
    overtime = winprob.sparkline_svg(_curve(overtime_from=30))

    def width(svg):
        return float(re.search(r"viewBox='0 0 ([\d.]+) ", svg).group(1))

    assert width(overtime) > width(regulation), (
        "an overtime game's chart is physically longer — that is Marc's second sentence")
    expected = winprob._CURVE_OT_BAND_UNITS * winprob._CURVE_PX_PER_UNIT
    assert abs((width(overtime) - width(regulation)) - expected) < 1.5, (
        "one overtime period must add exactly one band at the shared scale")

    # THE SHARED SCALE ITSELF: the fourth-quarter reference line is at the same x on both.
    def quarter_line_xs(svg):
        return sorted({float(x) for x in re.findall(r"<line x1='([\d.]+)' y1='2'", svg)})
    assert quarter_line_xs(regulation)[:5] == quarter_line_xs(overtime)[:5], (
        "the regulation reference lines must land identically, or the scale is not shared")


def test_the_PANEL_passes_the_truncation_flag_and_not_just_the_helper(monkeypatch):
    """🚨 §6, MODE 1: THE FIRST VERSION OF THE TEST ABOVE CAME BACK GREEN UNDER ITS OWN BREAK.

    Removing the flag from the cell renderer — `_sparkline_svg(points, reaches_final=True)`,
    unconditionally — left every assertion in
    `test_a_truncated_curve_is_never_labelled_with_a_final_value` passing, because that test
    calls the HELPER with the argument it wants. A helper that honours a parameter says nothing
    about whether the caller ever passes it. A133 hit the identical shape with the label placer
    and closed it the same way.

    ✅ SO THIS DRIVES THE PANEL. It builds the real column list through `_most_exciting`, finds
    the curve column, and formats a row whose published flag is False.
    """
    import contextlib
    import pandas as pd
    today = _today()

    class _Quiet:
        def __getattr__(self, name):
            return lambda *a, **k: None

    captured = []

    def capture_render(df, columns, *a, **k):
        captured.append(columns)

    def capture_ros(df, view, what, why, renderer=None, **k):
        if renderer is not None and df is not None and not df.empty:
            renderer(df)

    curve = _curve()
    curve["game_id"] = 7

    monkeypatch.setattr(today, "st", _Quiet())
    monkeypatch.setattr(today.states, "section", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(today.states, "render_or_state", capture_ros)
    monkeypatch.setattr(today.table, "render", capture_render)
    monkeypatch.setattr(today, "_win_probability_curves", lambda ids: curve)

    class _Scope:
        def describe(self):
            return "the fixture"

        def link(self, page, **extra):
            # ⚠️ A147. `_commentary` DRAWS THE DETAILS GLYPH NOW, so the double has to model the
            # one method the page actually calls on a scope. A stub that models less than the page
            # uses fails as an AttributeError INSIDE `states.section`, which catches it and draws
            # an Error card — the shape A141 shipped to production and A144 found.
            return f"/{page}?" + "&".join(f"{k}={v}" for k, v in extra.items())

    frame = pd.DataFrame([{
        "game_id": 7, "away_team_display": "Away U", "home_team_display": "Home U",
        "away_points": 15, "home_points": 44,
        "home_periods": 4, "away_periods": 4,
        "home_q1": 7, "home_q2": 14, "home_q3": 13, "home_q4": 10,
        "away_q1": 0, "away_q2": 7, "away_q3": 8, "away_q4": 0,
        "lead_changes_fourth_quarter": 2, "lead_changes_overtime": 0,
        "scoreboard_lead_changes_fourth_quarter": 1,
        "scoreboard_lead_changes_overtime": 0, "scoreboard_lead_changes": 2,
        "mean_distance_from_even_fourth_quarter_onward": 0.31, "lead_changes": 3,
        "excitement_index": 6.1,
        # THE GAME THE FLAG EXISTS FOR: Coastal Carolina at UTSA's shape — the feed stops
        # while the eventual winner is still near zero.
        "win_probability_curve_reaches_final_score": False,
        # A139, cfdb-main-R-934 — the side the final value belongs to.
        "home_abbreviation": "HOME",
    }])

    today._most_exciting(frame, _Scope())
    assert captured, "the panel handed no columns to table.render"
    columns = {c.field: c for c in captured[-1]}
    assert "curve" in columns, "the curve column vanished from the panel"

    cell = columns["curve"].format(frame.iloc[0])
    assert "cut</text>" in cell, (
        "the panel did not pass the truncation flag through to the chart — the helper honours "
        "it, which is a different claim")
    assert not _svg_label(cell).endswith("%"), (
        "a truncated curve must not print a final value even when the panel renders it")

    # ✅ AND THE OTHER DIRECTION, so the assertion above is not satisfied by a chart that never
    # labels anything. ⚠️ THE PANEL IS RE-RUN rather than the row mutated: A139 builds the label
    # map once from the frame the panel was given, which is the point — two call sites deriving
    # the same string is how a column ends up sized for a label the chart does not draw.
    captured.clear()
    complete = frame.copy()
    complete.loc[0, "win_probability_curve_reaches_final_score"] = True
    today._most_exciting(complete, _Scope())
    columns = {c.field: c for c in captured[-1]}
    cell = columns["curve"].format(complete.iloc[0])
    assert _svg_label(cell).endswith("%")
    assert "HOME" in cell, "cfdb-main-R-934: the visible label names the home side"


def test_the_final_value_names_the_home_side_and_not_the_away_one():
    """🚨 cfdb-main-R-934, AND NOTHING IN THE CODE WAS WRONG WHEN IT WAS FOUND.

    A138's own raster, row 1 of 2026 week 2:

        IOWA STATE   0 10 3 0 | 13
        IOWA         0 10 0 6 | 16        [curve] 94%

    **The 94% is IOWA's — the home side.** Every label was correct and the panel still told a
    reader the opposite of the truth, because the scoreboard deliberately puts the AWAY team on
    the TOP line (R-522) and the bare number sits nearest it. ⚠️ Worse, the `aria-label` already
    read *"Home win probability"*, so a screen-reader user was told which side it was and a
    sighted reader was not.

    ✅ THE ASSERTION IS THAT THE ABBREVIATION IS THE HOME SIDE'S, which is the half a break can
    invert without changing anything else on the chart.
    """
    winprob = _winprob()
    import pandas as pd
    points = _curve()
    row = pd.Series({"win_probability_curve_reaches_final_score": True,
                     "home_abbreviation": "IOWA", "away_abbreviation": "ISU"})

    text, is_cut = winprob.curve_label(row, points)
    assert not is_cut
    assert text.startswith("IOWA "), f"the label must lead with the HOME abbreviation: {text!r}"
    assert "ISU" not in text, "the away side's abbreviation must never appear on this label"
    assert text.endswith("%"), "and the number is still the number"

    svg = winprob.sparkline_svg(points, label=text, is_cut=is_cut)
    assert _svg_label(svg) == text, "the visible label is the one that was measured"
    assert "home side" in svg, "the aria-label must not say less than the pixels"


def test_the_label_falls_back_to_the_bare_percentage_rather_than_printing_none():
    """⚠️ A130's CHAIN ENDS IN "drop it rather than publish `None @ AUB`", AND THE SAME APPLIES.

    📊 `home_abbreviation` is null on 4.9% of `srv_game` and on **0 of the 1,895 games that can
    enter this panel** — measured in published serving, not assumed. So this branch is
    unreachable here today and is still the honest fallback: a chart label is no place for a
    twenty-character team name, and `None 94%` is worse than `94%`.
    """
    winprob = _winprob()
    import pandas as pd
    points = _curve()
    text, _ = winprob.curve_label(
        pd.Series({"win_probability_curve_reaches_final_score": True,
                   "home_abbreviation": None}), points)
    assert text.endswith("%") and "None" not in text, text
    assert " " not in text, "with no side to name, the label is just the number"


def test_the_curve_label_sits_left_of_the_final_point_and_buys_no_width():
    """🚨 A164. MARC'S SECOND SENTENCE IS AN ACCEPTANCE CRITERION, NOT A RATIONALE.

    > *"Can we change the label on the last data point to be on the left side of the data point
    > instead of the right? **That will tighten up the horizontal space.**"*

    ⚠️ **SO MOVING THE LABEL WITHOUT SHRINKING THE CHART WOULD FAIL THIS ASK EVEN THOUGH THE
    LABEL MOVED**, which is why the width is asserted here and not only the anchor.

    📊 A139 sized the gutter from the label's own length — `offset + len(text) * 5.4219 + trail`
    — which was right while the label sat in the margin. It no longer does, so a regulation chart
    is `2*pad + 176 + trail` for EVERY label: **182px, against 224 for `MICH 94%` before.**

    🚨 **THE LOAD-BEARING ASSERTION IS THAT TWO DIFFERENT LABELS PRODUCE THE SAME WIDTH.** That
    is the property that fails the moment anyone reintroduces a per-label gutter — a pinned 182
    alone would not, because a gutter sized for a short label could still land on it.
    """
    winprob = _winprob()
    points = _curve()

    assert winprob.chart_width(points) == 182, (
        "a regulation chart is 2*_CURVE_PAD + 176px of clock + _CURVE_LABEL_TRAIL")

    short = winprob.sparkline_svg(points, label="cut", is_cut=True)
    long = winprob.sparkline_svg(points, label="MICH 100%")
    assert "width='182'" in short and "width='182'" in long, (
        "the label must not buy width any more — it is inside the plot")

    # The anchor, and the side. `text-anchor='end'` with x BELOW the final point's x is what
    # puts the glyphs to its left; either alone would not.
    assert "text-anchor='end'" in long, "the label is anchored at its right edge"
    import re
    label_x = float(re.search(r"<text x='([\d.]+)'[^>]*text-anchor='end'", long).group(1))
    last_x = max(float(x) for x in re.findall(r"L([\d.]+),", long)) if "L" in long else None
    assert last_x is not None, "this test needs a drawn path to compare against"
    assert label_x < last_x, f"label at {label_x} is not left of the final point at {last_x}"


def test_the_win_probability_axis_is_fixed_and_reads_no_data():
    """🚨 A169 (cfdb-main-R-1318). MARC'S DIAGNOSIS WAS WRONG AND THIS PINS WHY, so no later
    round can quietly introduce the thing he feared.

    > **MARC, Site v07:** *"Y-axis should be fixed at -1 to 1. It looks like it's auto-adjusting
    > to fill the vertical space. That's a zoom that gives a false perception of the scale of
    > momentum swings."*

    📊 **IT IS ALREADY FIXED, MEASURED ON TWO REAL GAMES WITH VERY DIFFERENT RANGES:**

        401858447   win probability 0.747 … 1.000    curve spans 30.0px
        401862702   win probability 0.006 … 0.970    curve spans 57.9px
        midline in BOTH                              y = 32.0

    **An auto-fitting axis would stretch the narrow game to fill the band and both spans would
    be equal.** They are not, and the midline does not move.

    ⚠️ **WHAT HE IS ACTUALLY SEEING IS HIS OWN TWO ASKS**: the plotting band went 40px → 60px
    across A165 and A167, so the same swing draws 1.50× the pixels it did three rounds ago.
    **The scale did not change; the canvas did.**

    ✅ **THIS TEST ASSERTS THE PROPERTY, NOT THE PIXELS** — that the mapping is a pure function
    of one probability, so it cannot start consulting the series.
    """
    winprob = _winprob()
    pad, height = winprob.PAD, winprob.HEIGHT
    band = height - 2 * pad

    def midline_of(frame):
        winprob = _winprob()
        svg = winprob.sparkline_svg(frame, label="X 50%")
        import re
        flat = [float(m) for m in re.findall(r"<line[^>]*y1='([\d.]+)'[^>]*y2='\1'", svg)]
        return min(flat) if flat else None

    # 🚨 TWO FRAMES THAT DIFFER ONLY IN THEIR RANGE. A single fixture cannot tell a fixed axis
    # from an auto-fitting one — that is the whole point of the comparison (R-843).
    base = _curve()
    narrow = base.assign(home_win_probability=[0.75 + (i % 5) * 0.05
                                               for i in range(len(base))])
    wide = base.assign(home_win_probability=[(i % 20) / 19.0 for i in range(len(base))])
    assert narrow["home_win_probability"].max() - narrow["home_win_probability"].min() < 0.3
    assert wide["home_win_probability"].max() - wide["home_win_probability"].min() > 0.9

    assert midline_of(narrow) == midline_of(wide), (
        "the reference line moved between two games — the axis is fitting to the data")
    assert midline_of(narrow) == pad + band / 2, (
        "0.5 must land exactly on the band's midpoint")

    # And the drawn extents must DIFFER, or the curves were rescaled to fill the band.
    import re

    def span(frame):
        winprob = _winprob()
        ys = [float(y) for y in re.findall(
            r"[ML][\d.]+,([\d.]+)", winprob.sparkline_svg(frame, label="X 50%"))]
        return max(ys) - min(ys)
    assert span(wide) > span(narrow) * 1.4, (
        f"a 0.95-range game must draw a much taller curve than a 0.25-range one; "
        f"got {span(wide):.1f} vs {span(narrow):.1f} — that is an auto-fitting axis")

    # 🚨 AND `sy` MUST NOT LEARN TO READ THE FRAME. This is the regression that would reintroduce
    # exactly what Marc fears, and it would be invisible in a single-game render.
    source = open(winprob.__file__).read()
    body = source[source.index("    def sy(probability)"):source.index("    right = sx(")]
    for forbidden in (".min()", ".max()", "points", "plotted"):
        assert forbidden not in body.split("return")[-1], (
            f"sy consults {forbidden!r} — the axis would fit itself to the data")


def test_the_quarters_are_named_and_overtime_is_not_a_fifth_quarter():
    """🚨 A167 (cfdb-main-R-1311). > **MARC, v06:** *"label the x-axis with the quarters (1Q, 2Q,
    etc)."*

    ⚠️ **THE LABELS SIT INSIDE THE PLOT AND THAT IS A DENSITY DECISION, NOT A STYLE ONE.**
    Measured both ways at 1300px: inside costs **0px** — row 81.8px, unchanged; below grows the
    chart 64px -> 78px and the row to **91.4px**, which is **+110px per ten-row panel** and gives
    back most of what A165 returned when Marc asked for *"things more dense vertically"*.

    🚨 **AND OVERTIME IS NOT A QUARTER.** The chart draws a band per overtime period, so the
    labels read `OT`, `2OT`, `3OT` — **verified on a real 3-overtime game** (`401866418`), which
    renders `['1Q','2Q','3Q','4Q','OT','2OT','3OT']`. A sequence reading `5Q` would be wrong, and
    a fixture with no overtime cannot tell the two apart.
    """
    winprob = _winprob()
    import re

    def labels(svg):
        return re.findall(r"text-anchor='middle'[^>]*>([^<]*)</text>", svg)

    regulation = winprob.sparkline_svg(_curve(), label="MICH 63%")
    assert labels(regulation) == ["1Q", "2Q", "3Q", "4Q"], labels(regulation)

    # 🚨 A CURVE WITH REAL OVERTIME BANDS, or the OT branch fires on nothing (R-760).
    overtime = _curve(overtime_from=30)
    assert winprob._curve_bands(overtime) > 0, "this fixture must actually reach overtime"
    drawn = labels(winprob.sparkline_svg(overtime, label="PSU 51%"))
    assert drawn[:4] == ["1Q", "2Q", "3Q", "4Q"], drawn
    assert drawn[4] == "OT", f"the first overtime is OT, never 5Q: {drawn}"
    assert all(d.endswith("OT") for d in drawn[4:]), drawn
    assert "5Q" not in drawn


def test_the_final_percentage_pops_and_the_abbreviation_does_not():
    """🚨 A167. > **MARC, v06:** *"Increase the font of the final win % and make it blue to help
    it pop out."*

    ⚠️ **HE SAID "the final win %", NOT "the label"** — so the team abbreviation keeps its size
    and the percentage alone grows and takes the colour.

    📊 **"BLUE" IS A TOKEN AND ITS CONTRAST IS MEASURED**, in situ, with the stylesheets injected
    the way `theme.inject()` injects them: `rgb(31,111,235)` on white at **4.63:1** and
    `rgb(88,166,255)` on `#0e1117` at **7.48:1** — both AA for normal text.

    🚨 **AND `_curve_width` MUST NOT HAVE GROWN.** The label is anchored at its RIGHT edge and
    grows leftward into the plot, so a bigger number costs the chart nothing; A165 took the
    regulation chart 224px -> 182px as Marc's *"tighten up the horizontal space"*.
    """
    winprob = _winprob()
    import re
    svg = winprob.sparkline_svg(_curve(), label="MICH 63%")
    match = re.search(r"<tspan font-size='([\d.]+)' fill='([^']+)'[^>]*>([^<]+)</tspan>", svg)
    assert match, f"the percentage is not in its own tspan: {svg[-240:]}"
    size, fill, text = match.groups()
    assert float(size) > 9, f"the percentage must be bigger than the label's 9px, not {size}"
    assert fill == "var(--cfdb-link)", f"blue comes from the token, never a hex: {fill!r}"
    assert text == "63%", text
    assert "<tspan>MICH </tspan>" in svg, "the abbreviation keeps the base size and is not blue"
    assert winprob.chart_width(_curve()) == 182, "the bigger label must buy no width"

    # 🚨 THE `cut` BRANCH IS AN ABSENCE, NOT A VALUE, AND IS NOT DRESSED AS ONE.
    cut = winprob.sparkline_svg(_curve(), label="cut", is_cut=True)
    assert "<tspan" not in cut, "the truncation word must not be styled like a win probability"
    assert "var(--cfdb-link)" not in cut


def test_the_curve_is_as_tall_as_the_scoreboard_rows_it_sits_beside():
    """📊 A164. THE HEIGHT IS A MEASUREMENT OF THE CELL BESIDE IT.

    > **MARC, Today v04:** *"Stretch the y-axis to take up the same amount of space by the Away
    > and Home lines in the Scoreboard."*

    Measured in Chromium on the real panel at a 1300px viewport, BY CLASS rather than by
    position: `.cfdb-sb-away` top to `.cfdb-sb-home` bottom is **67.2px**. An earlier reading
    that started at the `thead` said 80.8 and would have made the chart too tall.

    🚨 **AND TOO TALL IS THE FAILURE THAT MATTERS**, which is why this pins an upper bound as
    well as the value: the scoreboard cell is what sets the row height, so a chart taller than
    the scoreboard's own 80.8px would re-lay out every row on the panel.
    """
    winprob = _winprob()
    # ⚠️ A165: 67 -> 64. The scoreboard's own vertical cell padding went to zero for density
    # (cfdb-main-R-1302) and the span it is measured against shrank with it — re-measured by
    # class in Chromium, NOT adjusted by the same amount the row changed.
    assert winprob.HEIGHT == 64, "the away-to-home span re-measured after the density pass"
    assert winprob.HEIGHT > 44, "this is the stretch Marc asked for, not a no-op"
    # 🚨 THE UPPER BOUND MOVED WITH THE SCOREBOARD, WHICH IS THE POINT OF HAVING ONE. The
    # scoreboard is 74.4px after the density pass; a chart taller than that starts driving the
    # row height and every scoreboard on the panel re-lays out.
    assert winprob.HEIGHT < 74.4, (
        "taller than the scoreboard and the chart starts driving the row height")
    svg = winprob.sparkline_svg(_curve(), label="MICH 94%")
    assert "height='64'" in svg, "the default must actually reach the drawn chart"


def test_most_exciting_layout_has_one_entry_per_column_and_the_scoreboard_is_widest():
    """🚨 A165 REWROTE THIS TEST RATHER THAN DELETING IT, AND THE REASON IS WHY IT EXISTED.

    A164 wrote `test_most_exciting_layout_pins_only_the_first_two_columns` to hold *"layout is
    `["26%", widest+12] + ["auto"]*6`"* — which pinned **an** arrangement rather than **the**
    rule, so the first correct change to the arrangement turned it red. ⚠️ **A test that blocks
    a correct change is encoding the wrong invariant**, and deleting it would have thrown away
    the real one with it.

    ✅ **THE INVARIANT THAT ACTUALLY MATTERS** is the one whose violation is invisible: `layout`
    becomes a `<colgroup>`, one `<col>` per entry, so a list that falls out of step with the
    columns misaligns every width by one — and only on a viewport wide enough for the pinned
    widths to bite.

    📊 A165's arrangement, and each number is measured rather than chosen:
    the scoreboard takes 40% because `.cfdb-sb-team` now needs 13rem inside it, and the three
    lead-change columns are 56px because their values are single digits and their labels were
    shortened to `4th qtr` / `OT` / `Game`.
    """
    import re
    source = open(_today().__file__).read()
    body = source[source.index("def _most_exciting("):source.index("def _favorite_margin(")]

    match = re.search(r'^    layout = (\[.+?\])\n', body, re.M | re.S)
    assert match, "the layout line moved; this test cannot see what it is asserting about"
    layout = eval(match.group(1), {},                        # noqa: S307 - a literal list
                  {"widest": 170, "scoreboard_px": 427,
                   "_SCOREBOARD_GUTTER_PX": 6})

    headers = re.findall(r'Col\("[a-z_]+", "([^"]+)"', body)
    assert headers == ["Scoreboard", "Win probability", "4th qtr", "OT", "Game",
                       "How close, late", "Excitement", "Commentary"], headers

    # 🚨 ONE ENTRY PER COLUMN. This is the assertion that cannot be checked by looking.
    assert len(layout) == len(headers), (
        f"{len(layout)} widths for {len(headers)} columns — the colgroup is out of step")

    # 🚨 A167: THE SCOREBOARD COLUMN IS DERIVED, NOT A PERCENTAGE (cfdb-main-R-1310).
    #
    # > **MARC, v06:** *"Scoreboard - unneccessary white space to the right of the scoreboard."*
    #
    # A165 set it to 40% to fix a truncation that was never in this column — its own measurement
    # was *"+54% width, ellipsised count UNCHANGED at eleven"*. 📊 A167 measured the scoreboard's
    # NATURAL width instead: 425.6px at four periods, 463.2px at five, and **identical at 6, 9
    # and 13** because `_quarter_cells` draws one overtime column rather than one per period.
    # **Leftover whitespace went 47.2px -> 8.8px at 1300px and 167.2px -> 8.8px at 1600px.**
    #
    # ⚠️ A PERCENTAGE IS WHAT MADE IT WORSE ON A WIDE SCREEN: 40% of a wider table is a wider
    # gap. A px width derived from the content cannot do that, which is why this asserts the
    # KIND and not just the number.
    assert layout[0].endswith("px"), (
        f"the scoreboard column must be derived from the scoreboard, not a share of the table: "
        f"{layout[0]}")
    assert 400 <= int(layout[0][:-2]) <= 500, layout[0]
    # ── A189: THE LAST SIX ARE FIXED, AND EACH IS WIDE ENOUGH FOR ITS OWN HEADER ────────────
    #
    # 🚨 THIS REPLACES A165's `<= 52.15px` RULE, AND THE TWO INSTRUCTIONS GENUINELY CONFLICT.
    #
    #     v06: "The Lead Change columns need to use less horizontal space. Reduce by at least
    #           50% horizontally."                                  -> pinned them at 52px
    #     v11: "...the last 6 columns get a fixed width and the table will have a horizontal
    #           scroll instead of forcing them to be super narrow, and then their headers take
    #           up a bunch of vertical space, making the table very wonky?"
    #
    # 📊 AT 52px THOSE HEADERS CANNOT FIT ON ONE LINE — measured in Chromium with the table's
    # own font: `4th qtr ⇅` is 58px and `Game ⇅` is 57px. **A165's width is the direct cause of
    # v11's complaint**, and the fix for one is the other's defect.
    #
    # ✅ v11 WINS, AND THE REASON IS NOT ONLY THAT IT IS NEWER: A165's cut was made when the
    # table had to fit the viewport, and v11 asks for a horizontal scroll, which removes the
    # scarcity the 50% was rationing. Horizontal space is no longer the constraint it was.
    #
    # ⚠️ SO THE INVARIANT IS "NO HEADER CAN WRAP", held as measured numbers rather than as a
    # ratio, because a ratio against a number nobody re-measures is how A165's rule outlived
    # its reason.
    fixed = layout[2:]
    assert all(w.endswith("px") for w in fixed), (
        f"the last six columns must be FIXED, not auto — that is the whole ask: {fixed}")
    # header text measured at 1600px in the table's own font, one line, including the ⇅ arrow
    header_px = {"4th qtr": 58, "OT": 38, "Game": 57,
                 "How close, late": 113, "Excitement": 88, "Commentary": 93}
    for label, width in zip(headers[2:], fixed):
        need = header_px[label]
        assert int(width[:-2]) >= need, (
            f"{label!r} is {width} but its header needs {need}px on one line — it will wrap, "
            f"which is the 'headers take up a bunch of vertical space' defect v11 reported")


def _rankings_frame():
    """A poll with a TIE, a team that leaves and returns, and a late entrant.

    ⚠️ ALL THREE ARE REAL SHAPES, NOT DECORATION: 2026 AP week 1 has two teams at rank 14, the
    gap is what `invalid="break-paths-filter-domains"` exists for, and a late entrant is what
    puts a left label somewhere other than week 1.
    """
    import pandas as pd
    rows = [
        ("Alpha", 1, 1), ("Alpha", 2, 2), ("Alpha", 3, 1),
        ("Bravo", 1, 2), ("Bravo", 2, 1), ("Bravo", 3, 2),
        ("Charlie", 1, 3), ("Charlie", 3, 3),            # unranked in week 2 — the gap
        ("Delta", 1, 3),                                  # tied with Charlie at week 1
        ("Echo", 2, 4), ("Echo", 3, 4),                   # enters late
    ]
    frame = pd.DataFrame(rows, columns=["team_display", "week", "rank"])
    # ⚠️ A165: THE COLOUR PAIR, AND `Echo`'s IS NULL ON PURPOSE. A team with no published colour
    # must fall back to the neutral this panel drew for everyone before — a fixture where every
    # team has a colour cannot test the branch that exists for the ones that do not (R-744).
    swatches = {"Alpha": ("#7a0019", "#c8102e"), "Bravo": ("#002b5c", "#4f86c6"),
                "Charlie": ("#154734", "#2e7d5b"), "Delta": ("#862633", "#d05a6e"),
                "Echo": (None, None)}
    frame["color_on_light"] = frame["team_display"].map(lambda t: swatches[t][0])
    frame["color_on_dark"] = frame["team_display"].map(lambda t: swatches[t][1])
    return frame


def _left_label_rows(spec):
    """The rows behind the LEFT-hand team labels, resolved through Altair's `datasets` block.

    🚨 A163 FOUND THAT A CHART'S DATA IS LIFTED OUT OF THE LAYER AND INTO A TOP-LEVEL `datasets`
    BLOCK, so a layer's own `data` is a NAME and reading it returns nothing. That cost that round
    a "rows: 0" it had to chase; resolving by name is the fix, once, here.

    The left labels are the text layer aligned `right` — the right-hand ones are aligned `left`.
    """
    datasets = spec.get("datasets", {})
    picture = spec["hconcat"][0]
    for layer in picture.get("layer", []):
        mark = layer.get("mark", {})
        if isinstance(mark, dict) and mark.get("type") == "text" and mark.get("align") == "right":
            data = layer.get("data", {})
            if "name" in data:
                return datasets[data["name"]]
            return data.get("values", [])
    raise AssertionError("no right-aligned text layer — the left labels are not in this spec")


def test_the_bump_chart_spec_serialises_and_keeps_its_gap_rule():
    """🚨 A164. THIS TEST EXISTS BECAUSE THE PANEL SHIPPED BROKEN FOR A FEW MINUTES AND NOTHING
    ELSE COULD SEE IT.

    Building the left-label layer with `scale=y.scale` read back a `_PropertySetter` rather than
    a scale, and the WHOLE SPEC failed to serialise — which on the page is an exception inside
    `states.section`, a handled Error card, and a green suite. **1,400 tests passed on it.**
    ⚠️ No other test in this repository builds this chart, so `to_dict()` is the only instrument
    that can fail here, and it now runs on every commit.

    ✅ **AND IT GUARDS THE GAP RULE IN THE SAME PASS** — `invalid="break-paths-filter-domains"`
    is what stops a line joining across a team's unranked weeks. Its own comment says the whole
    correctness of the gap rests on it, and a step interpolation makes a joined gap look MORE
    deliberate rather than less: a flat run at a rank the team did not hold.
    """
    import json
    today = _today()
    frame = _rankings_frame()
    current = frame[frame["week"] == 3].assign(delta="—", points=1, first_place_votes=0)

    captured = []
    original = today.st
    today.st = type("S", (), {"altair_chart": staticmethod(lambda c, **k: captured.append(c)),
                              "caption": staticmethod(lambda *a, **k: None)})
    try:
        today._bump_chart(frame, "AP Top 25", current)
    finally:
        today.st = original

    assert len(captured) == 1, "the bump chart drew nothing to serialise"
    spec = json.loads(captured[0].to_json())          # <- the assertion that matters

    blob = json.dumps(spec)
    assert '"break-paths-filter-domains"' in blob, (
        "the gap rule left the spec — a line would join across a team's unranked weeks")
    assert f'"{today._BUMP_INTERPOLATE}"' in blob, "the interpolation did not reach the mark"
    # 🚨 BOTH LABELS, AND THIS ASSERTION EXISTS BECAUSE A STAGED BREAK THAT DELETED THE RIGHT
    # ONE CAME BACK GREEN. Marc asked to *"Label the left of the line with the school name"* —
    # an ADDITION. ⚠️ The caption tells a reader that *"a team on the picture with no row beside
    # it was ranked earlier in the season and is not ranked now"*, and those are exactly the
    # teams the companion table does NOT name: drop the right label and the caption's own case
    # becomes unreadable.
    aligns = {layer["mark"]["align"] for layer in spec["hconcat"][0]["layer"]
              if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
              and "align" in layer["mark"]}
    assert aligns == {"left", "right"}, (
        f"the chart must carry BOTH endpoint labels; text aligns present: {aligns}")

    # 🚨 A176 (cfdb-main-R-1760). THIS PINNED `step-after` ON A164's MEASUREMENT AND NOW PINS
    # `linear` ON A176's. Both are real measurements and they answer DIFFERENT questions, which
    # is why this is a change of value rather than a correction of reasoning.
    #
    # 📊 A164 measured WHERE THE VERTICAL LANDS: step-after's turn is on the tick where the new
    # rank was published (x=449 and 722.3 against week centres 175.7/449/722.3), while
    # step-before turned a week early and step on no tick at all.
    #
    # 📊 A176 measured WHAT THE CHART COSTS TO READ, which A164 never did. Over AP Top 25, 2025
    # regular — 48 teams, 16 weeks:
    #
    #     coincident segments (two teams on one line)   0 of 335    <- the stated cause is not one
    #     step-after   590 segments   868 crossings     1.47 each
    #     linear       335 segments   389 crossings     1.16 each
    #
    # ⚠️ A step splits every rank change into a horizontal hold AND a vertical turn, and the
    # vertical crosses every horizontal between the two ranks. **The diagonal crosses 55% less
    # ink.** And Marc reversed his own v04 instruction to ask for it.
    #
    # ⚠️ THE COST IS REAL AND IS NOT HIDDEN: a diagonal draws a team at a rank it never held
    # BETWEEN ticks — the same objection A164 raised against `step-before`. The ticks stay
    # exact; the space between them is interpolated, and that trade is Marc's.
    assert today._BUMP_INTERPOLATE == "linear", (
        "linear halves the segment count and cuts crossings 55% (868 -> 389) on the real "
        "frame, and Marc asked for it in v09 after asking for right angles in v04; a step "
        "manufactures crossings by turning every rank change into a vertical through every "
        "rank between")


def test_exactly_one_producer_answers_which_theme_the_viewer_is_in():
    """🚨 A165 (cfdb-main-R-1303). A PROMOTION THAT LEAVES THE OLD COPY BEHIND IS THE §4.3 DEFECT
    IT EXISTS TO PREVENT, and *"I removed the old one"* is not a measurement.

    B136 built `_drive_dark_theme()` inside `matchup.py` for the drives accent. Today's poll
    chart needs the identical answer, so it moved to `lib/theme.py` — session A's — and both
    pages now call it. ⚠️ **This counts DEFINITIONS across the whole site**, because the failure
    mode is a second `def` appearing later that answers the same question slightly differently.
    """
    import pathlib
    import re
    site = pathlib.Path(_today().__file__).parent.parent
    defs, callers = [], []
    for f in sorted(site.rglob("*.py")):
        src = f.read_text()
        for m in re.finditer(r"^def (\w*(?:dark_theme|viewer_is_dark)\w*)", src, re.M):
            defs.append(f"{f.name}:{m.group(1)}")
        if "viewer_is_dark()" in src and f.name != "theme.py":
            callers.append(f.name)
    assert defs == ["theme.py:viewer_is_dark"], f"one producer, and it is theme.py's: {defs}"
    assert "matchup.py" in callers, "matchup.py must CALL it, not define its own"
    assert "today.py" in callers, "today.py is the second caller this promotion was for"


def test_the_poll_lines_carry_team_colour_and_a_missing_one_falls_back():
    """📊 A165 (cfdb-main-R-1304). Marc: *"Team colors will help."*

    🚨 **THE FALLBACK IS THE HALF A FIXTURE USUALLY CANNOT TEST**, so `Echo` publishes no colour
    at all. A team with nothing published keeps the neutral this panel drew for everyone before
    — it must not become invisible, and it must not silently take another team's swatch.

    ⚠️ **AND THE SCALE IS AN EXPLICIT domain/range PAIR, NOT A SCHEME.** A Vega scheme recycles
    once it runs out, which is the exact failure the panel's own design note warned about; a
    domain/range says each team's colour by name and cannot wrap around.
    """
    import json
    today = _today()
    frame = _rankings_frame()
    current = frame[frame["week"] == 3].assign(delta="—", points=1, first_place_votes=0)
    captured = []
    original = today.st
    today.st = type("S", (), {"altair_chart": staticmethod(lambda c, **k: captured.append(c)),
                              "caption": staticmethod(lambda *a, **k: None)})
    try:
        today._bump_chart(frame, "AP Top 25", current)
    finally:
        today.st = original
    spec = json.loads(captured[0].to_json())

    # 🚨 THE COLOUR MUST BE ON THE *LINE* MARK, AND A STAGED BREAK IS WHY THIS IS SPECIFIC.
    # A first draft read the scale off "any layer with a colour encoding" — so deleting the
    # colour from the LINES came back GREEN, because the points still carried one. **Marc asked
    # for the lines** (*"Team colors will help"* about a bump chart), and a coloured dot on a
    # grey line is not that (R-744).
    layers = spec["hconcat"][0]["layer"]

    def _mark(layer):
        m = layer.get("mark")
        return m.get("type") if isinstance(m, dict) else m
    lines = [layer for layer in layers if _mark(layer) == "line"]
    assert lines, "no line mark in the poll chart at all"
    assert "color" in lines[0].get("encoding", {}), (
        "the LINES carry no colour encoding — a coloured point on a grey line is not what was "
        "asked for")
    points = [layer for layer in layers if _mark(layer) == "circle"]
    assert points and "color" in points[0].get("encoding", {}), (
        "the points must match their line, or a line and its dots disagree")
    scales = [layer["encoding"]["color"]["scale"] for layer in layers
              if "color" in layer.get("encoding", {})]
    dom, rng = scales[0]["domain"], scales[0]["range"]
    assert len(dom) == len(rng), "domain and range must pair one-to-one"
    by_team = dict(zip(dom, rng))
    assert by_team["Alpha"] in ("#7a0019", "#c8102e"), by_team["Alpha"]
    assert by_team["Bravo"] in ("#002b5c", "#4f86c6"), by_team["Bravo"]
    # 🚨 Echo publishes nothing and must NOT come back as null, empty or another team's colour.
    assert by_team["Echo"] not in (None, "", by_team["Alpha"]), by_team["Echo"]
    assert by_team["Echo"].startswith("#"), f"the fallback must be a real colour: {by_team['Echo']}"


def test_tied_teams_share_one_left_label_because_there_is_no_room_for_two():
    """📊 A164 (cfdb-main-R-1145). MEASURED IN THE RASTER, TWICE, AND THE FIRST FIX FAILED.

    Two teams at the same rank get the same y. Drawn separately they overstrike exactly — 0.0px
    apart. ❌ Spreading them ∓0.45 of a rank separated *them* and put one 9.2px from the team a
    rank above: **the collision moved rather than cleared**, because a 16.8px rank pitch against
    ~13px of text has under 4px of slack.

    ✅ One label naming both is legible AND truer — they hold the same rank that week.
    """
    import json
    today = _today()
    frame = _rankings_frame()          # Charlie and Delta are both rank 3 in week 1
    current = frame[frame["week"] == 3].assign(delta="—", points=1, first_place_votes=0)
    captured = []
    original = today.st
    today.st = type("S", (), {"altair_chart": staticmethod(lambda c, **k: captured.append(c)),
                              "caption": staticmethod(lambda *a, **k: None)})
    try:
        today._bump_chart(frame, "AP Top 25", current)
    finally:
        today.st = original
    # 🚨 READ THE LEFT-LABEL LAYER ITSELF, NOT THE WHOLE SPEC. A first draft asserted
    # `'"Echo"' in json.dumps(spec)` and **a staged break that dropped every late entrant came
    # back GREEN** — because Echo also appears in the right-hand labels and in the companion
    # table. R-744: a break that comes back green is rewritten until it can fail.
    rows = _left_label_rows(json.loads(captured[0].to_json()))
    names = {r["team_display"] for r in rows}

    assert "Charlie · Delta" in names, (
        f"the two teams tied at rank 3 in week 1 must share one left label; got {names}")
    assert "Charlie" not in names and "Delta" not in names, (
        "a tied team must not ALSO be labelled on its own")
    # ⚠️ AND THE LATE ENTRANT IS LABELLED AT ITS OWN FIRST WEEK, not at week 1 — the half that
    # makes this a "first ranked week" label rather than a "week 1" label.
    echo = [r for r in rows if r["team_display"] == "Echo"]
    assert echo, f"a team that enters in week 2 still gets a left label; got {names}"
    assert echo[0]["week"] == 2, f"and it sits at ITS first week, not week 1: {echo[0]}"
    assert len(rows) == 4, f"four labels for five teams, one of them shared: {rows}"


# --- A138: the scoreboard (cfdb-main-R-906) ----------------------------------------------

def _scoreline_row(**overrides):
    row = {"away_team_display": "Away U", "home_team_display": "Home U",
           "away_points": 23, "home_points": 24,
           "home_periods": 4, "away_periods": 4,
           "home_q1": 7, "home_q2": 3, "home_q3": 4, "home_q4": 10,
           "away_q1": 0, "away_q2": 10, "away_q3": 3, "away_q4": 10}
    row.update(overrides)
    import pandas as pd
    return pd.Series(row)


def _scoreboard_team_order(html):
    """The team names in the order the scoreboard actually emits them.

    🚨 A144 MOVED THE NAME INSIDE A CELL AND THIS EXTRACTOR HAD TO FOLLOW IT — the row header now
    holds the shared team-identity cell (logo, rank badge, linked name, record) rather than a bare
    string, so `cfdb-sb-team'>([^<]*)</th>` matched nothing and every assertion below compared two
    empty lists. ⚠️ AN EXTRACTOR THAT STOPS FINDING ANYTHING IS THE WORST AVAILABLE FAILURE FOR A
    TEST LIKE THIS: `[] == []` would have passed on a scoreboard with the two sides SWAPPED, which
    is precisely R-522's law and precisely what B082 and B083 proved a presence assertion cannot
    see. It failed loudly only because the expectation is the two real names.

    ✅ SO IT READS THE NAME THE CELL ACTUALLY RENDERS — `.cfdb-team`, `table.team_cell`'s own span —
    which is STRONGER than the old match: it now proves the identity cell drew a name at all, in
    the right row, as well as proving the order.
    """
    cells = re.findall(r"cfdb-sb-team'>(.*?)</th>", html, re.S)
    found = [re.search(r"cfdb-team'>([^<]*)</span>", cell) for cell in cells]
    return [match.group(1) for match in found if match]


def test_away_is_above_home_in_every_scoreboard_under_every_sort():
    """🚨 MARC: "Sorting moves the games, not the rows within the game." THAT IS A GRAIN
    STATEMENT, NOT A PREFERENCE, and R-522 is the law it restates.

    ⚠️ B082 AND B083 BOTH PROVED A PRESENCE ASSERTION CANNOT SEE THIS. "The scoreboard has two
    rows" passes with them in either order. So this drives the page's REAL sort — `table.apply_sort`,
    the same function `table.render` calls — over every sortable column in both directions, and
    checks the rendered scoreboard of every game each time.

    ✅ AND IT FIRES: building the two lines from `sorted(...)` by points, or emitting home first,
    turns every assertion below red on the first column tried.
    """
    import pandas as pd
    today = _today()
    from lib import table as table_module

    frame = pd.DataFrame([
        _scoreline_row(away_points=10, home_points=38, away_team_display="A1",
                       home_team_display="H1"),
        _scoreline_row(away_points=45, home_points=3, away_team_display="A2",
                       home_team_display="H2"),
    ])
    columns = [table_module.Col("away_points", "Away"), table_module.Col("home_points", "Home")]

    for field in ("away_points", "home_points"):
        for order in ("asc", "desc"):
            ordered = frame.sort_values(field, ascending=(order == "asc"),
                                        na_position="last", kind="mergesort")
            for _, row in ordered.iterrows():
                names = _scoreboard_team_order(today._scoreboard(row))
                assert names == [row["away_team_display"], row["home_team_display"]], (
                    f"sorting by {field} {order} moved the home side above the away side")
    assert columns, "the sortable columns are the outer table's, never the scoreboard's"


def test_the_scoreboard_keeps_the_three_quarter_states_apart():
    """🚨 AC-G.32 SURVIVES THE LAYOUT CHANGE, WHICH IS THE THING A RESTRUCTURE LOSES QUIETLY.

        played and scoreless      `0`
        never played              NO COLUMN AT ALL — not a blank one
        score not held            an em dash in that position

    ⚠️ A BLANK CELL FOR "never played" AND A BLANK CELL FOR "we do not know" IS THE EXACT
    COLLAPSE `_quarter_cells` exists to prevent, and a grid is where it is easiest to commit.
    """
    today = _today()

    played = today._quarter_cells(_scoreline_row(home_q2=0), "home")
    assert ("2", "0") in played, "a scoreless quarter that was played reads 0"

    short = today._quarter_cells(_scoreline_row(home_periods=3, home_q4=None), "home")
    assert [label for label, _ in short] == ["1", "2", "3"], (
        "a three-period game has THREE columns, not four with a blank")

    unknown = today._quarter_cells(_scoreline_row(home_q3=None), "home")
    assert ("3", "\u2014") in unknown, "a quarter we do not have reads as an em dash"

    assert today._quarter_cells(_scoreline_row(home_periods=None), "home") is None, (
        "no period count at all is a fourth state and is not a scoreboard")

    # AND IN THE RENDERED GRID, not only in the helper.
    html = today._scoreboard(_scoreline_row(home_q3=None))
    assert ">\u2014</td>" in html, "the em dash has to survive into the cell"


def test_the_scoreboard_labels_overtime_and_never_folds_it_into_the_fourth():
    """🚨 A117's LESSON APPLIED TO THE DISPLAY. Jacksonville State at Ohio had TWO fourth-quarter
    lead changes and ELEVEN in overtime; a scoreboard that added the overtime points onto Q4
    would put the drama in a quarter where it did not happen, with every number still real.
    """
    today = _today()
    pairs = today._quarter_cells(
        _scoreline_row(home_periods=5, home_overtime_points=13, home_q4=10), "home")
    assert pairs[-1] == ("OT", "13"), "overtime is its own labelled column"
    assert ("4", "10") in pairs, "and the fourth quarter keeps its own number"

    html = today._scoreboard(_scoreline_row(home_periods=5, away_periods=5,
                                            home_overtime_points=13, away_overtime_points=7))
    assert ">OT</th>" in html, "the grid needs the label, not just the value"


def test_the_scoreboard_absorbed_four_columns_and_dropped_none():
    """🚨 MARC'S SENTENCE DESCRIBES THE SCOREBOARD AND THE CHART. IT DOES NOT SAY DELETE THE
    MEASUREMENTS — they are what the ordering claims, and the caption cites two of them by name.

    The eleven columns became eight: the matchup, the score and the two by-quarter lines are all
    inside the scoreboard cell. The six that carry a number or a link are untouched.
    """
    source = _code_only(SOURCE)
    # ⚠️ SCOPED TO THE PANEL. `Col("matchup", ...)` also exists in the line-movement panel, so a
    # whole-file grep answers "does this string appear" rather than "does THIS panel have that
    # column" — R-859's class, in a test.
    panel = source[source.index("def _most_exciting"):source.index("def _favorite_margin")]
    # ⚠️ A153 MOVED THESE THREE TO THEIR SCOREBOARD SIBLINGS (§3.3 MIGRATE). The property this
    # test protects is unchanged — the restructure must not silently DROP a column — so the names
    # move with the panel rather than the assertion being deleted.
    for field in ("scoreboard_lead_changes_fourth_quarter", "scoreboard_lead_changes_overtime",
                  "mean_distance_from_even_fourth_quarter_onward", "scoreboard_lead_changes",
                  "excitement_index"):
        assert f'Col("{field}"' in panel, f"{field} lost its column in the restructure"
    assert 'Col("espn", "Commentary"' in panel, "the ESPN link is a column, not a row link"
    assert 'Col("scoreboard", "Scoreboard"' in panel
    assert 'Col("matchup"' not in panel and 'Col("away_line"' not in panel, (
        "the absorbed columns must be gone from this panel, not duplicated")
    assert len(re.findall(r"Col\(", panel)) == 8, (
        "eleven columns became eight: four absorbed into the scoreboard, and none dropped")


def test_the_panel_survives_the_curve_view_being_unpublished(monkeypatch):
    """🚨 R-748 — ASSERT UPSTREAM, DEGRADE DOWNSTREAM — AND A RESTRUCTURE IS EXACTLY THE EDIT
    THAT BREAKS THIS QUIETLY.

    `srv_game_win_probability_play` is the SECOND view behind this panel and the supplementary
    one: if it has not been published, the ranking, the scoreboard and the ESPN links are all
    still correct and worth showing. `curves` is bound BEFORE the `states.section` block for
    that reason — `section` swallows the exception and the code below still runs, so an unbound
    name there turns a handled degradation into a crash.

    ⚠️ AND THE SCOREBOARD IS NOW THE THING THAT MUST SURVIVE IT. Before A138 the panel degraded
    to ten rows of quarter columns; now it degrades to ten scoreboards, which is strictly more
    of the page depending on the binding staying where it is.
    """
    import contextlib
    import pandas as pd
    today = _today()

    class _Quiet:
        def __getattr__(self, name):
            return lambda *a, **k: None

    captured = []

    def capture_ros(df, view, what, why, renderer=None, **k):
        if renderer is not None and df is not None and not df.empty:
            renderer(df)

    @contextlib.contextmanager
    def swallowing_section(*a, **k):
        try:
            yield
        except Exception:
            pass

    def unpublished(_ids):
        raise RuntimeError('relation "srv_game_win_probability_play" does not exist')

    monkeypatch.setattr(today, "st", _Quiet())
    monkeypatch.setattr(today.states, "section", swallowing_section)
    monkeypatch.setattr(today.states, "render_or_state", capture_ros)
    monkeypatch.setattr(today.table, "render",
                        lambda df, columns, *a, **k: captured.append((df, columns)))
    monkeypatch.setattr(today, "_win_probability_curves", unpublished)

    class _Scope:
        def describe(self):
            return "the fixture"

        def link(self, page, **extra):
            # ⚠️ A147. `_commentary` DRAWS THE DETAILS GLYPH NOW, so the double has to model the
            # one method the page actually calls on a scope. A stub that models less than the page
            # uses fails as an AttributeError INSIDE `states.section`, which catches it and draws
            # an Error card — the shape A141 shipped to production and A144 found.
            return f"/{page}?" + "&".join(f"{k}={v}" for k, v in extra.items())

    frame = pd.DataFrame([{
        "game_id": 7, "away_team_display": "Away U", "home_team_display": "Home U",
        "away_points": 23, "home_points": 24, "home_periods": 4, "away_periods": 4,
        "home_q1": 7, "home_q2": 3, "home_q3": 4, "home_q4": 10,
        "away_q1": 0, "away_q2": 10, "away_q3": 3, "away_q4": 10,
        "lead_changes_fourth_quarter": 6, "lead_changes_overtime": 0,
        "scoreboard_lead_changes_fourth_quarter": 3,
        "scoreboard_lead_changes_overtime": 0, "scoreboard_lead_changes": 4,
        "mean_distance_from_even_fourth_quarter_onward": 0.12, "lead_changes": 14,
        "excitement_index": 5.0, "win_probability_curve_reaches_final_score": True,
    }])

    today._most_exciting(frame, _Scope())
    assert captured, "the panel rendered nothing at all with the curve view unpublished"
    df, columns = captured[-1]
    by_field = {c.field: c for c in columns}
    row = df.iloc[0]
    assert "Home U" in by_field["scoreboard"].format(row), "the scoreboard must still render"
    assert "ESPN" in by_field["espn"].format(row), "the links must still work"
    assert by_field["curve"].format(row) == "\u2014", (
        "the curve column degrades to an em dash rather than taking the panel down")


def test_the_panel_still_passes_no_row_link():
    """⚠️ `table.render` WRAPS A CELL IN THE ROW'S ANCHOR WHEN THERE IS ONE, and nested anchors
    are invalid HTML with the OUTER one winning — the reader would click "ESPN" and stay on the
    site, and it would look fine. The restructure is exactly the edit that introduces a row link.
    """
    source = _code_only(SOURCE)
    panel = source[source.index("def _most_exciting"):source.index("def _favorite_margin")]
    assert "link_builder" not in panel, (
        "a row link would silently break the ESPN column — see _espn_link's docstring")


# --- the upsets section (R-711) ---------------------------------------------------------

def _code_only(source: str) -> str:
    """The module's source with `#` comment lines removed.

    🚨 A SOURCE-GREP ASSERTION MUST SCAN WHAT RUNS, NOT WHAT IS WRITTEN ABOUT IT. A123 removed
    a duplicated list and recorded the removed expressions in a comment — which is exactly the
    right thing to leave behind, and it made a raw grep count three occurrences of a filter that
    appears once in the code. Deleting the comment to satisfy the grep would have been the wrong
    repair: the test was measuring the file, and the claim is about the program.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#"))


def _graded(*rows):
    """Graded games as `_recap_lists` builds them, after the derived columns exist."""
    import pandas as pd
    return pd.DataFrame([
        {"favorite": f, "opponent": o, "spread": s, "fav_margin": m,
         "ats": m - s, "fav_win_prob": w}
        for f, o, s, m, w in rows])


def test_the_upsets_list_is_ordered_by_how_likely_the_loser_was_to_win():
    """🚨 THE ORDERING IS THE CLAIM THE HEADING MAKES, and it is the only thing separating
    "biggest upsets" from "a list of favorites that lost".

    ⚠️ AND THE FIRST VERSION OF THIS TEST WAS WORTHLESS, WHICH THE STAGED BREAK PROVED RATHER
    THAN THE REVIEW. It built its own frame, applied its own `sort_values`, and asserted the
    result — so it asserted that PANDAS SORTS, never that the page does. Flipping the page to
    `ascending=True` left all thirty tests green. That is this file's own recorded failure
    ("the second draft constructed its own Col list ... it was testing a list the test wrote
    rather than the one the page writes") repeated in a new panel, and §6's fourth way a staged
    break proves nothing.

    ✅ SO THIS CALLS THE REAL `_recap_lists` AND READS THE FRAME IT HANDS TO `table.render`.
    Sorting ascending leaves every row real and the count right, and turns the list into THE
    LEAST SURPRISING UPSETS while it is still headed "Biggest" — the picture is the only place
    that shows, so the order is what has to be asserted.

    The live shape this mirrors, 2026 week 2: Oregon were 23.5-point favorites given a 91.3%
    market-implied chance and lost to Oklahoma State, while Idaho at 3.5 and 60.3% is the least
    surprising of the seventeen.
    """
    import sys
    import pandas as pd

    site_path = str(ROOT / "site")
    path_added = site_path not in sys.path
    if path_added:
        sys.path.insert(0, site_path)
    saved_st = sys.modules.get("streamlit")
    stub, _calls = _stub_streamlit()
    sys.modules["streamlit"] = stub
    try:
        _reload_all()
        page = sys.modules["views.today"]
        assert page.st is stub, "views.today is not talking to the stub — the reload failed"

        rendered = []
        page.table.render = lambda df, columns, *a, **k: rendered.append(df)

        # Three favorites that lost: the market gave them 91.3%, 65.1% and 60.3%.
        games = pd.DataFrame([
            _upset_row("Idaho", "Lamar", spread=-3.5, win_prob=0.603, margin=-6),
            _upset_row("Oregon", "Oklahoma State", spread=-23.5, win_prob=0.913, margin=-8),
            _upset_row("Oklahoma", "Michigan", spread=-4.5, win_prob=0.651, margin=-7),
        ])
        page._recap_lists(games, _Scope())

        assert rendered, "the panel rendered no table at all"
        order = list(rendered[0]["favorite"])
        assert order == ["Oregon", "Oklahoma", "Idaho"], (
            f"the upsets list must lead with the least likely loss, got {order}")
    finally:
        if saved_st is not None:
            sys.modules["streamlit"] = saved_st
        else:
            sys.modules.pop("streamlit", None)
        _reload_all()
        if path_added:
            sys.path.remove(site_path)


class _Scope:
    """The minimum a recap panel asks of its scope."""
    week = 9
    season = 2026

    def describe(self):
        return "2026 week 9"


def _upset_row(favorite, opponent, spread, win_prob, margin):
    """One graded game where the HOME side was favored and lost by `margin`."""
    return {
        "home_team_display": favorite, "away_team_display": opponent,
        "spread_favorite_side": "home", "moneyline_favorite_side": "home",
        "favorite_definitions_disagree": False,
        "spread_at_close": spread, "spread_current": spread,
        "actual_margin": -margin, "actual_margin_home_perspective": margin,
        "market_implied_home_win_probability": win_prob,
        "market_implied_away_win_probability": 1 - win_prob,
    }


def test_the_recap_section_no_longer_ships_one_set_of_games_twice():
    """🚨 THE TWO REMOVED LISTS WERE IDENTICAL BY CONSTRUCTION, not merely overlapping.

        missed = graded[graded["ats"] < 0].sort_values("ats").head(10)
        covers = graded[graded["ats"] < 0].sort_values("ats").head(10)

    Character for character the same expression, so the section spent two of its three lists on
    one set of games and buried the upsets underneath them. This pins the collapse: exactly one
    `ats < 0` list survives.
    """
    code = _code_only(SOURCE)
    # 🚨 A189 REMOVED THE SURVIVOR TOO — Marc: *"Biggest Underdog covers / Remove this
    # section"*. R-711 collapsed three lists to two; this takes the second, so ZERO `ats < 0`
    # lists remain and the section is the upsets alone. The invariant is stronger, not weaker:
    # it was "no duplicate", it is now "none at all".
    assert code.count('graded[graded["ats"] < 0]') == 0, (
        "the underdog covers list was removed in A189; an `ats < 0` list reappearing means it "
        "came back")
    assert "Underperformers" not in code, (
        "Marc read that heading and asked for what was underneath it; the section leads with "
        "the upsets now")
    assert "**Biggest upsets**" in code


def test_ats_is_gone_now_that_its_only_reader_is():
    """⚠️ THE ROUND REMOVED A PRESENTATION, NOT A MEASURE.

    `ats` is computed in the page — `fav_margin - spread` — which is §4.2.1's line, and moving
    it upstream needs a game-grain column that does not exist yet (`srv_game_team` carries
    `ats_margin_final` at game x TEAM grain). That is a model round, deliberately not this one.
    This test records that the column still has exactly one consumer, so that round knows how
    small it is.
    """
    code = _code_only(SOURCE)
    # 🚨 A189 REMOVED `ats` ALTOGETHER, AND THIS TEST'S JOB IS NOW THE OPPOSITE ONE.
    #
    # It tracked how small the §4.2.1 violation was, so a later model round would know the
    # cost of moving it upstream. Marc removed the only list that read it, so there is nothing
    # left to move: computing `fav_margin - spread` in the page for NO consumer would be the
    # violation with none of the benefit. **The test now holds it gone.**
    assert '"ats"' not in code, (
        "`ats` is metric arithmetic in a page (§4.2.1) and its only reader — the underdog "
        "covers list — was removed in A189. If it is needed again it comes from "
        "srv_game_team.ats_margin_final, not from here.")
    assert code.count('graded["ats"] = ') == 0, (
        "`ats` must not be computed for nobody — A189 removed its only reader")


def test_the_home_side_draws_below_the_midline():
    """🚨 A171 (cfdb-main-R-1600). THE AXIS AND THE SCOREBOARD BESIDE IT MUST AGREE ABOUT WHICH
    TEAM IS "UP", AND FOR THE WHOLE LIFE OF THE PANEL THEY DID NOT.

    > **MARC:** *"Win probability y-axis needs to be reversed. It should be aligned so that the
    > Home team's Win Probability is positive on the bottom (b/c that team is represented on
    > bottom on the Scoreboard)."*

    📊 **HE WAS RIGHT, AND IT WAS A CORRECTNESS DEFECT RATHER THAN A PREFERENCE.** `_scoreboard`
    emits `side_row(away…)` then `side_row(home…)` — R-522's away-over-home law — so the cell
    beside this chart puts home on the bottom. Measured on two real games before the fix:

        home dominated  401778306   160 of 160 points ABOVE the midline
        away dominated  401628396   146 of 147 points BELOW it

    ⚠️ **THE ASSERTION IS ON A PROBABILITY WELL AWAY FROM 0.5, BECAUSE 0.5 IS THE FIXED POINT OF
    THE FLIP** (R-843: a pinned value must MOVE under the break). A fixture sitting at the
    midline passes both orientations and proves nothing.
    """
    winprob = _winprob()

    def y_at(probability):
        frame = _curve(n=12)
        frame["home_win_probability"] = probability
        svg = winprob.sparkline_svg(frame)
        ys = [float(y) for y in re.findall(r"[ML][\d.]+,([\d.]+)", svg)]
        mid = float(re.search(
            r"<line x1='[\d.]+' y1='([\d.]+)'[^>]*stroke-dasharray='2 2'", svg).group(1))
        return sum(ys) / len(ys), mid

    home_y, mid = y_at(0.9)
    away_y, _ = y_at(0.1)
    assert home_y > mid, (
        f"home at 90% must draw BELOW the midline (larger y is lower on screen); "
        f"got y={home_y:.1f} against a midline of {mid:.1f} — the axis is back to front")
    assert away_y < mid, (
        f"home at 10% means the AWAY side is winning, which draws ABOVE the midline; "
        f"got y={away_y:.1f} against {mid:.1f}")

    # The midline is the fixed point: 0.5 lands on it in either orientation, which is exactly
    # why it cannot be the thing asserted on.
    even_y, _ = y_at(0.5)
    assert abs(even_y - mid) < 0.5, f"0.5 must sit on the midline; got {even_y} vs {mid}"


def test_the_curve_lobes_take_their_own_teams_colour_and_the_line_stays_neutral():
    """🚨 A171 (cfdb-main-R-1602). Marc's second ask, and his own pick of the three he offered.

    > **MARC:** *"shade the area with the color of team favored at that point."*
    > **MARC, choosing:** *"1 - start with your preference, the fill."*

    ✅ **THE STROKE STAYS NEUTRAL DELIBERATELY** — a 1.1px line is the harder contrast case, and
    on dark **100 of 1,898 games (5.27%) publish the two sides in exactly the same colour**.
    Colouring the line as well would be a second thing to get wrong on those games.

    📊 **CONFINEMENT WAS PROVED WITH PIXELS, NOT WITH THE MARKUP** — a midline-crossing game
    rasterised at 8x gave 0 home-coloured pixels above the midline and 0 away-coloured below.
    This test pins the structure that produced it, because a raster is not something CI can run.
    """
    winprob = _winprob()
    svg = winprob.sparkline_svg(_curve(), home_color="#0000ff", away_color="#ff0000")

    # Two clips, and the HOME one is the lower half — that is the half A171 moved home into.
    clips = dict((cid, (float(y), float(h))) for cid, y, h in re.findall(
        r"<clipPath id='([^']+)'>\s*<rect x='0' y='([\d.]+)' width='[\d.]+' "
        r"height='([\d.]+)'", svg))
    home_clip = [c for c in clips if c.endswith("-home")]
    away_clip = [c for c in clips if c.endswith("-away")]
    assert len(home_clip) == 1 and len(away_clip) == 1, clips
    assert clips[home_clip[0]][0] > clips[away_clip[0]][0], (
        "the home clip must start LOWER down the band than the away clip")

    # Each colour is bound to its own clip, and not to the other one.
    bindings = dict((cid, colour) for colour, cid in re.findall(
        r"<path d='[^']*' fill='(#[0-9a-f]{6})' clip-path='url\(#([^)]+)\)'", svg))
    assert bindings.get(home_clip[0]) == "#0000ff", bindings
    assert bindings.get(away_clip[0]) == "#ff0000", bindings

    # The line is NOT coloured.
    assert not re.search(r"<polyline[^>]*stroke='(?!currentColor)", svg), (
        "the polyline must stay currentColor — Marc chose the fill, not the line")

    # One <defs> for the whole chart even when overtime splits it into several segments.
    assert winprob.sparkline_svg(_curve(overtime_from=30), home_color="#0000ff",
                                 away_color="#ff0000").count("<defs>") == 1

    # And with no colours supplied, nothing changes: one neutral fill, no clips at all.
    plain = winprob.sparkline_svg(_curve())
    assert "<clipPath" not in plain and "fill='currentColor'" in plain


def _yardage_frame():
    """A board whose three columns have DIFFERENT maxima, so one denominator is detectable."""
    import pandas as pd
    return pd.DataFrame([
        {"team_display": "Alpha", "total_yards": 800, "rushing_yards": 400,
         "passing_yards": 400},
        {"team_display": "Beta", "total_yards": 400, "rushing_yards": 100,
         "passing_yards": 300},
        {"team_display": "Gamma", "total_yards": 200, "rushing_yards": 50,
         "passing_yards": 150},
    ])


def test_the_spark_bars_share_one_denominator_and_it_is_the_total_column():
    """🚨 A175 (cfdb-main-R-1750). THE THING MARC ASKED FOR FIVE ROUNDS AGO, AND THE ONE CLAUSE
    THAT IS EASY TO GET WRONG.

    > **MARC, Today v04:** *"Can we add horizontal spark bars in the Total, Rush, and Pass
    > cells. Make them all proportionate and relative to the max of the Total column. Bars from
    > the left. The number in the cell right aligned, not at the end of the bar."*

    🚨 **ONE DENOMINATOR FOR ALL THREE COLUMNS.** Scaled per column, Alpha's 400 rushing yards
    and Alpha's 400 passing yards would BOTH draw full width — and so would a 90-yard rushing
    game on a board whose best rusher had 90. **The bars would stop comparing anything.**

    📊 The fixture's maxima differ on purpose — total 800, rush 400, pass 400 — so the two
    readings are 50% and 100% and cannot be confused (R-843: the pinned value must MOVE).
    """
    today = _today()
    frame = _yardage_frame()
    # A189 (cfdb-main-R-1930): the denominator carries Marc's 1.15 headroom now — *"so the
    # label isn't in the chart"*. The PROPERTY is unchanged: one denominator, from the Total
    # column of the RENDERED frame. Asserted against the constant rather than a literal, so the
    # test moves with the number instead of pinning a stale one.
    assert today._spark_max(frame) == pytest.approx(800 * today._SPARK_HEADROOM)

    def width(row, field):
        cell = today._spark_cell(row, field, frame)
        found = re.search(r"width:([\d.]+)%", cell)
        return float(found.group(1)) if found else None

    leader = frame.iloc[0]
    # 🚨 A189: THE LEADER NO LONGER FILLS THE CELL, AND THAT IS THE POINT OF THE CHANGE.
    #
    # > **MARC:** *"...1.15 of the table MAX? That will push the size of the bars down a little
    # > bit so the label isn't in the chart."*
    #
    # At 100% the longest bar ran under its own right-aligned value. 1/1.15 = 87.0%, so the
    # headroom is 13% of the cell — measured here rather than asserted as "less than 100",
    # which would pass on any shrinkage including a broken one.
    assert width(leader, "total_yards") == pytest.approx(100 / today._SPARK_HEADROOM, abs=0.1)
    assert width(leader, "total_yards") < 100.0, (
        "the leader's bar must leave room for its label — that is the whole ask")
    # 🚨 THE RATIOS BETWEEN ROWS ARE UNCHANGED, which is the property that matters: every bar
    # still shares ONE denominator. 400 against TOTAL's 800 is half of whatever the leader is.
    assert width(leader, "rushing_yards") == pytest.approx(
        width(leader, "total_yards") / 2, abs=0.1), (
        "the rush bar is scaled to its own column's max — Marc asked for Total's")
    assert width(leader, "passing_yards") == pytest.approx(
        width(leader, "total_yards") / 2, abs=0.1)

    # And a smaller row scales the same way.
    assert width(frame.iloc[1], "total_yards") == pytest.approx(
        width(leader, "total_yards") / 2, abs=0.1)
    assert width(frame.iloc[2], "rushing_yards") == pytest.approx(
        50 / 800 * 100 / today._SPARK_HEADROOM, abs=0.1)


def test_the_spark_number_is_right_aligned_in_the_cell_not_at_the_bars_end():
    """⚠️ MARC'S LAST CLAUSE, AND IT IS A SEPARATE REQUIREMENT: *"The number in the cell right
    aligned, not at the end of the bar."*

    A value riding the bar's end would encode the same quantity twice and line up with nothing
    down the column. The bar is drawn BEHIND the number — absolutely positioned, out of the
    text flow — so the digits sit at the cell's right edge whatever width the bar takes.
    """
    today = _today()
    frame = _yardage_frame()
    cell = today._spark_cell(frame.iloc[1], "total_yards", frame)

    assert "cfdb-spark-bar" in cell and "cfdb-spark-value" in cell
    # The bar element carries the width; the value element never does.
    bar = re.search(r"<span class='cfdb-spark-bar'[^>]*></span>", cell).group(0)
    value = re.search(r"<span class='cfdb-spark-value'>.*?</span>", cell).group(0)
    assert "width:" in bar and "width:" not in value
    # The bar is EMPTY — the number is not inside it, which is what "not at the end" means.
    assert bar.endswith("></span>")

    source = (ROOT / "site" / "lib" / "theme.py").read_text()
    assert ".cfdb-spark { position:relative; display:block; text-align:right; }" in source, (
        "the cell's own right alignment is what puts the number at the cell's edge")
    assert "position:absolute" in source.split(".cfdb-spark-bar")[1][:200], (
        "the bar must be out of the text flow, or it pushes the number off the right edge")


def test_the_spark_denominator_comes_from_the_rendered_frame_and_degrades():
    """⚠️ A175. THE MAX IS A PROPERTY OF WHAT IS ON SCREEN, not of the relation — the board is
    `depth`-limited and scope-filtered, so the denominator MOVES with the depth radio and the
    week. **That is correct: the bars compare the rows Marc is looking at.**

    🚨 AND THE TWO DEGENERATE FRAMES MUST NOT DIVIDE BY ZERO. An empty or all-null board draws
    NO bar rather than a full one — a full-width bar on no data is a picture of a number that
    does not exist.
    """
    import pandas as pd
    today = _today()

    assert today._spark_max(pd.DataFrame()) == 0.0
    assert today._spark_max(None) == 0.0
    all_null = pd.DataFrame([{"total_yards": None}, {"total_yards": None}])
    assert today._spark_max(all_null) == 0.0

    # With no denominator the cell still renders its NUMBER, and draws no bar.
    cell = today._spark_cell({"total_yards": 250}, "total_yards", pd.DataFrame())
    assert "cfdb-spark-bar" not in cell and "250" in cell

    # A single row is its own max — honest, because it is the max of what is shown.
    single = _yardage_frame().head(1)
    assert today._spark_max(single) == pytest.approx(800 * today._SPARK_HEADROOM)

    # And the denominator really does follow the frame it is handed.
    assert today._spark_max(_yardage_frame().head(2)) == pytest.approx(800 * today._SPARK_HEADROOM)
    assert today._spark_max(_yardage_frame().tail(1)) == pytest.approx(200 * today._SPARK_HEADROOM)


def _scatter_rows():
    """Two teams at opposite extremes, so every direction claim has a detectable answer."""
    return [{"team": "Best", "x": 100.0, "y": 600.0, "games": 3,
             "accent": "light-dark(#111111, #eeeeee)"},
            {"team": "Worst", "x": 500.0, "y": 200.0, "games": 3,
             "accent": "light-dark(#222222, #dddddd)"}]


def test_the_scatter_puts_more_gained_at_the_top_and_fewer_allowed_at_the_right():
    """🚨 A176 (cfdb-main-R-1761). > **MARC, v09:** *"Switch Y and X axis, so that Y is Yards
    gained (top is better), and X is yards allowed (right is smaller and better)."*

    ⚠️ **BOTH AXES RUN AGAINST THE NAIVE MAPPING AND THAT PAIR IS THE POINT.** Y is gained and
    more is better, so it increases UPWARD — an inversion, because SVG's y grows downward. X is
    allowed and fewer is better, so it decreases RIGHTWARD — also an inversion. Either one
    alone would break *"up and to the right is stronger"*, which is how a scatter is read
    before a word of it.

    📊 PROVED ON THE REAL PANEL TOO, week 3 2026: Miami's 702.5 gained draws at cy=47 (top) and
    LSU's 142.5 allowed at cx=501 (right).
    """
    today = _today()
    svg = today._scatter_svg(_scatter_rows(), (100.0, 500.0), (200.0, 600.0))
    marks = dict((t, (float(cx), float(cy))) for cx, cy, t in re.findall(
        r"<circle class='cfdb-sc-pt' cx='([\d.]+)' cy='([\d.]+)'[^>]*>"
        r"<title>([A-Za-z]+)", svg))
    assert set(marks) == {"Best", "Worst"}, marks

    assert marks["Best"][1] < marks["Worst"][1], (
        "600 yards gained must draw ABOVE 200 — Y is the offence now and up is more")
    assert marks["Best"][0] > marks["Worst"][0], (
        "100 yards allowed must draw RIGHT of 500 — X is the defence now and right is fewer")


def test_the_scatter_captions_moved_with_their_axes():
    """⚠️ A176. A caption left on the old axis is `cfdb-main-R-1082`'s defect, and it cost a
    round. The x caption is the DEFENCE now and the y caption is the OFFENCE."""
    today = _today()
    svg = today._scatter_svg(_scatter_rows(), (100.0, 500.0), (200.0, 600.0))
    captions = re.findall(r"cfdb-sc-axis[^>]*>([^<]+)<", svg)
    assert len(captions) == 2, captions
    horizontal, vertical = captions
    assert "allowed" in horizontal and "gained" not in horizontal, horizontal
    assert "gained" in vertical and "allowed" not in vertical, vertical
    assert "↑" in vertical, "the vertical caption keeps its direction arrow"


def test_the_scatter_marks_are_unfilled_and_carry_the_teams_own_colour():
    """> **MARC, v09:** *"Make these unfilled circles. Color by Team color"*

    🚨 THE CHART LOOKS NO COLOUR UP. It receives a finished `light-dark(...)` string from the
    caller (`identity.accent_color`), which the BROWSER resolves — so a mid-session theme flip
    is correct with no Python in the loop (cfdb-main-R-1601). 📊 `color_on_light` and
    `color_on_dark` are 0.00% null across the 1,932 team-weeks this panel can draw.
    """
    today = _today()
    svg = today._scatter_svg(_scatter_rows(), (100.0, 500.0), (200.0, 600.0))
    circles = re.findall(r"<circle class='cfdb-sc-pt'[^>]*>", svg)
    assert len(circles) == 2
    for circle in circles:
        assert "fill='none'" in circle, "Marc asked for unfilled circles"
        assert "stroke='light-dark(" in circle, circle

    # And a row with no colour falls back rather than emitting an empty stroke.
    plain = today._scatter_svg([{"team": "X", "x": 300.0, "y": 300.0, "games": 1}],
                               (100.0, 500.0), (200.0, 600.0))
    assert "stroke='currentColor'" in plain, plain


def test_the_real_profile_panel_puts_the_strong_team_top_right_and_says_so(monkeypatch):
    """🚨 A176 (cfdb-main-R-1763). MY FIRST FIVE SCATTER TESTS ALL CALLED `_scatter_svg`
    DIRECTLY, AND A NINTH STAGED BREAK CAME BACK GREEN THROUGH ALL OF THEM.

    📊 The break swapped `_profile`'s two source lines back — `xs` to yards FOR, `ys` to yards
    ALLOWED — which is the whole feature Marc asked for, and **67 tests passed.** The drawing
    knows which direction each axis runs; only the caller knows which MEASURE is on it, and
    nothing was asserting the caller.

    ✅ SO THIS DRIVES THE REAL `_profile` and reads what it actually emitted. R-768's trap is
    the reason it invokes the panel instead of rebuilding the row list: a test that assembles
    its own `rows` and calls the drawing asserts that this test can swap two names.

    ⚠️ AND IT CAUGHT A SECOND DEFECT THE SVG TESTS COULD NOT SEE. `_profile` writes a THIRD
    caption, in prose, through `st.caption` — it read *"the vertical axis runs downward so
    fewer yards allowed is higher"*, which is a description of the chart before the swap.
    `cfdb-main-R-1082`'s defect exactly, in the one place I had not looked.
    """
    import contextlib          # local, matching the two other panel-driving tests in this file

    today = _today()

    frame = pd.DataFrame([
        # Strong: most yards gained AND fewest allowed -> must land top-right.
        {"team_display": "Strong", "team_slug": "strong", "team_id": 1, "conference": "SEC",
         "week": 9, "games_counted": 4, "total_yards_for_per_game": 600.0,
         "total_yards_allowed_per_game": 100.0, "color_on_light": "#111111",
         "color_on_dark": "#eeeeee", "logo_url": "l.png", "as_of_ts": None},
        # Weak: the mirror image -> bottom-left.
        {"team_display": "Weak", "team_slug": "weak", "team_id": 2, "conference": "SEC",
         "week": 9, "games_counted": 4, "total_yards_for_per_game": 200.0,
         "total_yards_allowed_per_game": 500.0, "color_on_light": "#222222",
         "color_on_dark": "#dddddd", "logo_url": "w.png", "as_of_ts": None},
    ])

    written = []

    class _Quiet:
        def markdown(self, body, *a, **k):
            written.append(("markdown", str(body)))

        def caption(self, body, *a, **k):
            written.append(("caption", str(body)))

        def __getattr__(self, name):
            return lambda *a, **k: None

    monkeypatch.setattr(today, "st", _Quiet())
    monkeypatch.setattr(today.states, "section", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(today.table, "as_of_caption", lambda *a, **k: None)
    monkeypatch.setattr(today, "_yardage_profile", lambda scope: frame)

    today._profile(_Scope(), 25)

    svg = next(body for kind, body in written if kind == "markdown" and "cfdb-sc-pt" in body)
    marks = dict((t, (float(cx), float(cy))) for cx, cy, t in re.findall(
        r"<circle class='cfdb-sc-pt' cx='([\d.]+)' cy='([\d.]+)'[^>]*>"
        r"<title>([A-Za-z]+)", svg))
    assert set(marks) == {"Strong", "Weak"}, marks

    # The whole feature, asserted through the real panel: gained on Y, allowed on X.
    assert marks["Strong"][1] < marks["Weak"][1], (
        "the team gaining 600 must draw ABOVE the one gaining 200 — Y is yards GAINED")
    assert marks["Strong"][0] > marks["Weak"][0], (
        "the team allowing 100 must draw RIGHT of the one allowing 500 — X is yards ALLOWED")

    # And the hover reads gained first, in the order Marc named the axes.
    assert "Strong — 600.0 gained, 100.0 allowed" in svg, svg[:400]

    # 🚨 The prose caption is the third place the orientation is stated, and it was wrong.
    note = next(body for kind, body in written if kind == "caption")
    assert "runs downward" not in note, (
        "this sentence described the chart before A176's swap")
    assert "yards GAINED, so higher is more" in note, note
    assert "further right is FEWER yards" in note, note


def test_nothing_in_the_stylesheet_fills_the_scatter_marks_back_in():
    """🚨 A176 (cfdb-main-R-1764). MY OWN TEST ASSERTED `fill='none'` IN THE SVG SOURCE AND
    PASSED, AND THE BROWSER DREW EVERY MARK FILLED.

    📊 `theme.CSS` carried `.cfdb-sc-pt { fill:currentColor; fill-opacity:.45; }` — and **a CSS
    declaration beats a presentation attribute**, so the `fill='none'` on the mark lost to a
    stylesheet written when the marks WERE filled. Only the raster showed it; that is R-855 and
    B109's finding, third instance.

    ⚠️ SO THE GUARD IS ON THE STYLESHEET, NOT ON THE MARK. Asserting the attribute again would
    re-assert the thing that was already true. **The two have to agree, and the one that can
    silently win is the one to pin.**
    """
    _today()                     # puts `site/` on sys.path, as every test in this file does
    from lib import theme

    rules = [ln.strip() for ln in theme.CSS.splitlines() if ".cfdb-sc-pt" in ln]
    assert rules, "the scatter mark rule has gone — find out why before deleting this test"
    body = " ".join(rules)
    assert "fill:none" in body.replace(" ", ""), (
        f"the stylesheet must not fill a mark Marc asked to be unfilled: {body}")
    assert "fill:currentcolor" not in body.replace(" ", "").lower(), (
        f"this is the exact declaration that beat the mark's own fill='none': {body}")


def test_the_scatter_draws_its_median_lines_from_the_frame_it_was_given():
    """🚨 A178 (cfdb-main-R-1853). > **MARC, v10:** *"Add bolder lines for the median values
    and label."*

    ✅ THE MEDIAN IS A PROPERTY OF THE RENDERED FRAME, NOT A PUBLISHED QUANTITY. §4.2.1's
    deciding test is *how many consumers can this number have*, and the answer here is one —
    this drawing. Same standing as `_spark_max` (cfdb-main-R-1750).

    ⚠️ AND IT MUST MOVE WITH THE FRAME, which is the half a static assertion would miss: the
    panel is week-scoped and conference-filtered, so a median computed once and reused would
    be a number about teams that are not on screen.
    """
    today = _today()

    rows = [{"team": "A", "x": 100.0, "y": 200.0, "games": 1},
            {"team": "B", "x": 300.0, "y": 400.0, "games": 1},
            {"team": "C", "x": 500.0, "y": 600.0, "games": 1}]
    svg = today._scatter_svg(rows, (100.0, 500.0), (200.0, 600.0))
    assert "median 300" in svg, svg[:300]
    assert "median 400" in svg
    assert svg.count("cfdb-sc-median'") == 2, "one vertical and one horizontal"

    # The label names its population, so a reader is never told "median" without the n.
    assert "over 3 teams shown" in svg

    # 🚨 DROP THE MIDDLE TEAM AND THE MEDIAN MUST MOVE. Without this the test would pass on a
    # constant (R-843: the value has to move under the thing it claims to measure).
    fewer = today._scatter_svg(rows[:1] + rows[2:], (100.0, 500.0), (200.0, 600.0))
    assert "median 300" in fewer, "median of 100 and 500 is still 300"
    assert "over 2 teams shown" in fewer
    moved = today._scatter_svg(
        [{"team": "A", "x": 100.0, "y": 200.0, "games": 1},
         {"team": "B", "x": 200.0, "y": 250.0, "games": 1}], (100.0, 500.0), (200.0, 600.0))
    assert "median 150" in moved, moved[:300]


def test_the_scatter_gridlines_are_every_hundred_yards_and_muted():
    """⚠️ A178. > **MARC, v10:** *"Mute (lighter by 50%) down the current gridlines and reduce
    them to every 100 yard increments."*

    ⚠️ THE STEP IS AN ARGUMENT AND THE DOMAIN ROUNDS TO IT, so both had to move together — a
    100-step ladder over a domain rounded to 50s puts the bounds off the ladder, which is the
    chart standard §0.2 property that makes two renders comparable.
    """
    _today()
    import inspect

    from lib import theme
    from views import today as t

    signature = inspect.signature(t._scatter_svg)
    assert signature.parameters["x_step"].default == 100
    assert signature.parameters["y_step"].default == 100

    svg = t._scatter_svg([{"team": "A", "x": 150.0, "y": 250.0, "games": 1}],
                         (100.0, 500.0), (200.0, 600.0))
    # 100..500 inclusive at a 100 step is five gridlines, not nine.
    assert svg.count("cfdb-sc-grid") == 5 + 5, svg.count("cfdb-sc-grid")

    rule = [ln for ln in theme.CSS.splitlines() if ".cfdb-sc-grid" in ln and "stroke" in ln]
    assert rule and "stroke-opacity:.07" in rule[0], rule


def test_the_card_grid_reaches_todays_cards_and_nothing_else():
    """🚨 A178 (cfdb-main-R-1856). THE REFLOW IS A CHANGE TO A SHARED STYLESHEET, AND THE
    PROMPT ASKED FOR MATCHUP TO BE PROVED UNTOUCHED RATHER THAN ASSERTED.

    📊 `.cfdb-card` now carries `display:grid` with four fixed tracks. A CSS class selector is
    global, so the question is which pages draw an element with that exact class:

        matchup.py    ZERO references to any cfdb-card* class — its player card is built from
                      `identity.player_row`, which this round does not touch
        schedule.py   `cfdb-cardgrid` and `cfdb-gamecard` — neither is matched by `.cfdb-card`,
                      because a class selector matches a whole class name and not a prefix
        today.py      the only consumer

    ⚠️ A PREFIX IS NOT A MATCH AND THAT IS THE WHOLE RISK HERE. `cfdb-cardgrid` LOOKS like it
    would be caught by `.cfdb-card` to anyone reading quickly, which is exactly why this is a
    test and not a sentence in a report.
    """
    views = ROOT / "site" / "views"
    emitters = sorted(
        path.name for path in views.glob("*.py")
        if re.search(r"class='cfdb-card[' ]", path.read_text()))
    assert emitters == ["today.py"], (
        f"a second page now draws `.cfdb-card` and A178's four-track grid reaches it: "
        f"{emitters}")

    # And the shared row Matchup builds its own card from is untouched by this round.
    assert "cfdb-card" not in (views / "matchup.py").read_text(), (
        "matchup.py has started using the card classes — the grid would reflow session B's "
        "page, which is the collision §3 exists to prevent")
