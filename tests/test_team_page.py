"""The Team page's Roster tab — A172, the first round of the Team-page programme.

🚨 MARC'S REASON FOR PUTTING THIS AHEAD OF EVERYTHING ELSE, and it is the one that matters:
*"We need Team page to mature a bit before the site is shareable."* This project is a
job-application artefact, so *not shareable* is the defect that makes every other improvement
worth less.

> **MARC, v07:** *"Roster — table format Columns, split by offense, defense, special teams —
> Number, Name, Position, Ht, Wt, Class, Hometown"*

⚠️ EVERY TEST HERE STUBS `query`. CI's `flake8 + pytest` job has no serving database, which
A111 learned by turning CI red once.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_harness  # noqa: E402


def _player(position, **over):
    base = {"full_name": "A Player", "position": position, "jersey": 7,
            "class_year_display": "SR", "height_display": "6-3", "height_inches": 75,
            "weight_pounds": 210, "hometown_display": "Somewhere, XX",
            "as_of_ts": pd.Timestamp("2026-09-18", tz="UTC")}
    base.update(over)
    return base


def _draw(rows, season=2026, slug="a-team"):
    """The REAL `_roster`, with the query stubbed. Returns the captured markup."""
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        team.query = lambda sql, params=None: pd.DataFrame(rows)
        team._roster(season, slug)
        render_harness.assert_no_error_card(captured, "the team roster")
        return "\n".join(captured)


def _sections(html):
    return re.findall(r"<h4 class='cfdb-roster-unit'>([^<]+)</h4>", html)


def _row_counts(html):
    return [body.count("<tr") for body in re.findall(r"<tbody>(.*?)</tbody>", html, re.S)]


def test_every_roster_row_lands_in_exactly_one_section():
    """🚨 A172 (cfdb-main-R-1650). A PARTITION, NOT FOUR FILTERS — cfdb-wta-R-1192's defect.

    ⚠️ **ASSERTED ON WHAT THE PAGE DRAWS, not on a re-run of its own mapping.** R-768: a test
    that rebuilds the grouping and checks its own arithmetic asserts that `pandas` groups, which
    it does. The claim here is that **no player disappears between the frame and the screen** —
    so the rows are counted in the rendered tables.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, _cap, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        every_position = [p for _, positions in team.ROSTER_UNITS for p in positions]

    rows = ([_player(p) for p in every_position]
            + [_player(None), _player("?"), _player("ZZ-NOT-A-POSITION")])
    html = _draw(rows)

    drawn = sum(_row_counts(html))
    assert drawn == len(rows), (
        f"{len(rows)} players went in and {drawn} were drawn — a roster that silently drops a "
        f"player is worse than one that groups them oddly")


def test_an_unmapped_position_lands_in_unlisted_rather_than_vanishing():
    """🚨 A172 (cfdb-main-R-1651). THE SOURCE ADDS ABBREVIATIONS AND HAS ALREADY DONE IT TWICE.

    📊 `EDGE` and `NT` were added after the map was first written. **And live serving carries
    two more the sample analysis did not have: `ATH` (5 rows) and `KR` (1).** They land in
    `Unlisted`, where a reader can see them, rather than being filtered out of all four sections
    and disappearing from the roster.

    ⚠️ `KR` is plainly a special-teams position. **Extending the map is a football judgement and
    therefore Marc's** (§2.1), so A172 reported it rather than taking it — and this test pins the
    behaviour that makes the next one visible instead of silent.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, _cap, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        assert team.roster_unit("KR") == team.UNLISTED_UNIT
        assert team.roster_unit("ATH") == team.UNLISTED_UNIT
        assert team.roster_unit("SOMETHING-NEW") == team.UNLISTED_UNIT
        # The two absences the map deliberately merges, and the merge is the documented choice.
        assert team.roster_unit(None) == team.UNLISTED_UNIT
        assert team.roster_unit("?") == team.UNLISTED_UNIT
        # A known one must NOT fall through, or the assertions above prove nothing.
        assert team.roster_unit("QB") == "Offense"
        assert team.roster_unit("EDGE") == "Defense"
        assert team.roster_unit("P") == "Special teams"

    html = _draw([_player("QB"), _player("KR")])
    assert "Unlisted" in _sections(html), (
        "an unmapped position must appear under Unlisted, not disappear")
    assert sum(_row_counts(html)) == 2


def test_an_empty_unlisted_section_is_not_drawn():
    """⚠️ A172. An empty `Unlisted` heading on a fully-listed roster is a hole reserved for
    something that does not exist — B103's ruling on the omitted first name, and AC-G.11's rule
    that an absence must say WHICH absence it is. A heading with nothing under it says neither.
    """
    fully_listed = _draw([_player("QB"), _player("LB"), _player("P")])
    assert _sections(fully_listed) == ["Offense", "Defense", "Special teams"], (
        "a fully-listed roster must draw exactly three sections, in Marc's order")

    with_unknowns = _draw([_player("QB"), _player(None)])
    assert _sections(with_unknowns) == ["Offense", "Unlisted"], (
        "Unlisted appears only when it has rows — and then it must appear")


def test_a_unit_with_nobody_in_it_is_not_drawn_either():
    """⚠️ The same rule, applied to the three named units. A team with no listed kickers has no
    `Special teams` heading rather than an empty one that reads as a rendering failure.
    """
    assert _sections(_draw([_player("QB"), _player("LB")])) == ["Offense", "Defense"]
    assert _sections(_draw([_player("P")])) == ["Special teams"]


def test_the_height_column_sorts_on_inches_and_displays_the_string():
    """🚨 A172 (cfdb-main-R-1652). `height_display` IS A STRING LIKE `6-3`, AND A COLUMN THAT
    SORTS ON IT PUTS `6-10` BEFORE `6-3` — lexical order on a number that is not one.

    ✅ `table.render` sorts on the Col's own `field`, so the field is `height_inches` and
    `render` draws `height_display`. **The sort key and the shown value are different columns**,
    which is the sentence the next reader needs.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, _cap, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        height = [c for c in team.ROSTER_COLUMNS if c.label == "Ht"]
        assert len(height) == 1, "exactly one height column"
        column = height[0]
        assert column.field == "height_inches", (
            f"the height column must SORT on inches, not on {column.field!r} — "
            f"'6-10' sorts before '6-3' as a string")
        assert column.render is not None, "and it must DISPLAY the human string"
        assert column.render({"height_display": "6-3", "height_inches": 75}) == "6-3"

        # The lexical trap itself, stated as data: these two are in the wrong order as strings
        # and the right order as inches.
        assert "6-10" < "6-3", "the string order this column must not use"
        assert 70 < 75, "the numeric order it does use"

    # And the column order is Marc's, verbatim.
    with render_harness.streamlit_stubbed() as (_st, _cap, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        assert [c.label for c in team.ROSTER_COLUMNS] == [
            "#", "Name", "Pos", "Ht", "Wt", "Class", "Hometown"]


def test_the_player_name_is_not_a_link_in_this_round():
    """🚨 A172 (cfdb-main-R-1653). THE PROMPT SAID *"there is no player page"* AND THERE IS —
    `players.py` reads `params.get("player")` and queries `srv_player_stats` by `player_slug`,
    and this tab used to link to it. **The measurement replaced the reason, not the decision.**

    📊 ON LIVE SERVING, roster players with a row in `srv_player_stats`:

        2024   12,984 of 22,843   56.84%
        2025   13,646 of 30,072   45.38%
        2026   12,082 of 31,070   38.89%

    🚨 **So for the current season three names in five led to a page with nothing on it** — the
    "link to nowhere" `table.team_link` already refuses to build.

    ✅ THE FIX WORTH HAVING IS A PUBLISHED FLAG, NOT A JOIN: the site reads one relation per
    query (G-2), so this page cannot ask whether a player has stats. A `has_player_stats` boolean
    on `srv_team_roster` would let the name link where it resolves and stay plain where it does
    not. That is a dbt round, named in A172's report.
    """
    html = _draw([_player("QB", full_name="Some Player")])
    assert "Some Player" in html
    assert "/players" not in html, (
        "the roster must not link to the Players page while 61% of 2026 names resolve to "
        "nothing there — a name that looks clickable and leads nowhere is worse than plain text")
    assert "cfdb-cell-link" not in html and "<a " not in html, (
        "no anchors in the roster at all this round")


def test_the_two_empty_roster_states_read_differently():
    """AC-G.11. *"We do not collect rosters for that season"* and *"this team has no roster"* are
    different statements, and only one of them is true at a time.
    """
    before = _draw([], season=2019)
    assert "2024 onward" in before and "2019" in before, before[:200]

    current = _draw([], season=2026)
    assert "No roster recorded" in current, current[:200]
    assert "2024 onward" not in current, (
        "a collected season must not claim the season is out of scope")


def test_the_roster_lives_on_the_roster_tab_and_nothing_claims_it_is_unbuilt():
    """🚨 A172 (cfdb-main-R-1654). THE ROSTER TAB SAID "NOT BUILT YET" WHILE THE ROSTER WAS
    RENDERING ONE TAB TO THE LEFT.

    📊 Measured on the live page before this round: `tabs[3]` — the one labelled **Roster** —
    drew `states.degraded("dim_athlete", "Rosters need the athlete dimension and the player
    facts.")`, and `_roster` was called from `tabs[1]`, under the game log, where it drew 119
    players for Ohio State 2026. **A reader who clicked Roster was told the feature did not
    exist.**

    ⚠️ **THE FILE ALREADY CARRIED THE RULE, eight lines below the card**, written for the Trends
    tab on 2026-09-02: *"a site that explains why it cannot do something it CAN now do teaches
    the reader to stop looking, which is a worse failure than saying nothing."* R-768 again — a
    comment recording a trap does not prevent it.

    🚨 BY AST, NOT BY SUBSTRING. `team.py` now discusses `dim_athlete` at length in the comment
    explaining this very fix, so `"dim_athlete" in source` is true and always will be. The claim
    is about a CALL, so the call is what gets read.
    """
    import ast
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "team.py").read_text()
    tree = ast.parse(source)

    degraded_subjects = [
        node.args[0].value for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "degraded"
        and node.args and isinstance(node.args[0], ast.Constant)]
    assert "dim_athlete" not in degraded_subjects, (
        "the Roster tab must not claim it is waiting on dim_athlete — the roster renders")

    # And `_roster` is called exactly once, from the tab whose label is Roster.
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_roster"]
    assert len(calls) == 1, f"_roster must be called once, found {len(calls)}"

    labels = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "tabs"]
    assert len(labels) == 1, "one st.tabs call"
    names = [e.value for e in labels[0].args[0].elts]
    assert names.index("Roster") == 3, f"tab order changed: {names}"

    # The `with tabs[3]:` block is the one that contains the call — read the enclosing `with`.
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        item = node.items[0].context_expr
        if not (isinstance(item, ast.Subscript) and getattr(item.value, "id", "") == "tabs"):
            continue
        index = item.slice.value if isinstance(item.slice, ast.Constant) else None
        holds_roster = any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_roster"
                           for n in ast.walk(node))
        if holds_roster:
            assert index == names.index("Roster"), (
                f"_roster is drawn under tabs[{index}] ({names[index]}), not under Roster")
            break
    else:
        raise AssertionError("no `with tabs[...]` block contains the _roster call")


def test_no_dataset_label_names_a_view_no_panel_reads():
    """🚨 A174 (cfdb-main-R-1706). A LABEL FOR A VIEW NOTHING READS IS A LABEL THAT CANNOT BE
    WRONG, WHICH IS WHY NOTHING WOULD EVER CATCH IT.

    📊 A174 replaced the Schedule tab's `srv_team_game_log` read with the two relations the
    Scores and Schedule layouts actually use — and that left `DATASETS["srv_team_game_log"]`
    labelling a view **no panel reads any more**. Measured: 1 orphan before, 0 after.

    ⚠️ AND THIS IS THE *ONLY* REGISTRY CLAIM A174 MAKES, deliberately. The prompt asked for
    `lib/datasets.py` to "name the pages that read" each relation; **its own docstring forbids
    exactly that**: *"THIS IS A LABEL TABLE, NOT A PANEL-TO-VIEW TABLE, and the distinction is
    load-bearing. Which view a panel reads is declared exactly once, in that panel's own
    `states.section(...)` call."* 📊 And readership is many-to-many — `srv_game` is read by six
    views — while `registry.PAGES` maps a page to ONE view. **A hand-maintained readership map
    would be a second source for something derivable from the SQL, which is this project's
    most expensive failure mode.** So this asserts the one thing that IS cheap and true.
    """
    from lib.datasets import DATASETS
    read = set()
    views = Path(__file__).resolve().parents[1] / "site" / "views"
    for path in views.glob("*.py"):
        read |= set(re.findall(r"from\s+(srv_\w+)", path.read_text()))
    orphans = sorted(set(DATASETS) - read)
    assert not orphans, (
        f"these relations carry a reader-facing label and no panel reads them: {orphans}")
    assert len(DATASETS) >= 12, "the label table emptied out; this test would pass on nothing"


def _schedule_tab(played_rows, upcoming_rows, season=2026, slug="a-team"):
    """The REAL `_schedule_tab`, with each section's query stubbed by relation.

    ⚠️ STUBBED BY WHICH RELATION THE SQL NAMES, not by call order. The two sections read two
    different views, and a stub that answered by position would pass if they were swapped —
    which is the defect the section is built to avoid in the first place.
    """
    import importlib
    import pandas as pd
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        team = importlib.reload(importlib.import_module("views.team"))

        def fake(sql, params=None):
            if "from srv_game_team" in sql:
                return pd.DataFrame(played_rows)
            if "from srv_game" in sql:
                return pd.DataFrame(upcoming_rows)
            raise AssertionError(f"unexpected relation in: {sql[:80]}")

        team.query = fake
        team._schedule_tab(season, slug, "A Team")
        render_harness.assert_no_error_card(captured, "the team schedule tab")
        return "\n".join(captured)


def _played(**over):
    # ⚠️ TZ-AWARE ON PURPOSE. `fmt._local` REFUSES a naive timestamp — R-643: "guessing a zone
    # for it is what rendered every kickoff four hours early" — and serving publishes instants.
    # A fixture carrying a naive one holds a value production never produces, and the first
    # draft of this file did exactly that and drew an error card.
    base = {"week": 3, "game_id": 1, "game_date": pd.Timestamp("2026-09-12", tz="UTC"),
            "opponent": "Rival", "opponent_team_slug": "rival", "opponent_logo_url": None,
            "opponent_rank": None, "opponent_conference": "SEC", "is_home": True,
            "is_neutral_site": False, "result": "W", "points_for": 31,
            "points_against": 17, "margin": 14, "is_completed": True,
            "as_of_ts": pd.Timestamp("2026-09-18", tz="UTC")}
    base.update(over)
    return base


def _upcoming(**over):
    base = {"week": 4, "game_id": 2, "start_date": pd.Timestamp("2026-09-19", tz="UTC"),
            "venue": "A Stadium", "is_neutral_site": False,
            "home_team_slug": "a-team", "away_team_slug": "other",
            "home_team_display": "A Team", "away_team_display": "Other",
            "home_rank": None, "away_rank": None, "spread_at_close": -6.5,
            "spread_current": -7.0, "over_under": 52.5, "network_abbreviation": "ESPN",
            "is_completed": False, "as_of_ts": pd.Timestamp("2026-09-18", tz="UTC")}
    base.update(over)
    return base


def test_the_schedule_tab_draws_two_continuous_sections_in_marcs_order():
    """🚨 A174 (cfdb-main-R-1705). > **MARC, v07:** *"Schedule tab — Layout from Scores/Schedule
    page, but 2 continuous sections. Completed games use Score layout. Future games use
    Schedule layout"*

    **Completed above, upcoming below, one scroll — no tabs, no expander.**
    """
    html = _schedule_tab([_played()], [_upcoming()])
    assert _sections(html) == ["Completed", "Upcoming"], _sections(html)
    # The Scores layout's own words, from workbook.SCORES_COLUMNS — the one declaration the
    # Scores page and its sheet both read (AC-15.8).
    assert "Pts for" in html and "Pts against" in html
    # The Schedule layout's market columns.
    assert "Spread (home)" in html and "Total" in html


def test_each_section_is_absent_rather_than_empty_and_the_three_shapes_are_real():
    """🚨 AC-G.11. A heading over nothing says neither *"no games"* nor *"none yet"*.

    📊 ALL THREE SHAPES EXIST IN LIVE SERVING and A174 rendered each:

        Alabama 2026   2 played, 10 upcoming   -> BOTH sections
        Alabama 2025  15 played,  0 upcoming   -> Completed only
        Harvard 2026   0 played, 10 upcoming   -> Upcoming only
    """
    assert _sections(_schedule_tab([_played()], [])) == ["Completed"]
    assert _sections(_schedule_tab([], [_upcoming()])) == ["Upcoming"]

    both_empty = _schedule_tab([], [])
    assert _sections(both_empty) == []
    assert "No games recorded" in both_empty, both_empty[:200]


def test_the_opponent_cell_reads_is_home_and_marks_a_neutral_site():
    """AC-8.3 in one cell, and the neutral site is the case that earns it: *"vs"* rather than a
    bare name is the difference between a bowl game and a home game read at a glance.

    ⚠️ A174 REPLACED `_opponent`, which read the game log's `venue_role`. `srv_game_team`
    spells the same fact `is_home`, and the old helper had no other caller — so it was deleted
    rather than left as a second opponent cell nobody calls.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, _cap, _charts):
        team = importlib.reload(importlib.import_module("views.team"))
        assert not hasattr(team, "_opponent"), (
            "the game-log opponent helper still exists with no caller")
        assert team._opponent_cell(_played(is_home=True)) == "Rival"
        assert team._opponent_cell(_played(is_home=False)) == "@ Rival"
        assert team._opponent_cell(_played(is_home=False, is_neutral_site=True)) == "vs Rival"
        # And the upcoming side picks the OTHER team, from srv_game's two-sided row.
        assert team._upcoming_opponent(_upcoming(), "a-team") == "Other"
        assert team._upcoming_opponent(_upcoming(), "other") == "@ A Team"


def test_each_section_reads_one_relation_and_the_tab_never_joins():
    """🚨 G-2: one relation per query. **Two SECTIONS are two tables, not one table stitched
    from two reads** — which is what the prompt forbade and what a join would be.

    📊 THE GATING MEASUREMENT, on live published serving, is why there are two relations at
    all: `srv_team_game_log` carries neither the market nor the opponent's slug, logo or rank;
    `srv_game_team` is complete for the Scores layout; `srv_game` is complete for the Schedule
    layout. **No single relation carries both layouts' inputs.**
    """
    import ast
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "team.py").read_text()
    node = next(n for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name == "_schedule_tab")
    sqls = [a.value for c in ast.walk(node) if isinstance(c, ast.Call)
            for a in c.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
            and "select" in a.value.lower()]
    assert len(sqls) == 2, f"expected two queries, found {len(sqls)}"
    for sql in sqls:
        relations = set(re.findall(r"\bfrom\s+(srv_\w+)", sql))
        assert len(relations) == 1, f"a query names {relations}; G-2 allows one"
        assert " join " not in sql.lower(), "no joins on a page"
        assert "limit" in sql.lower(), "AC-G.39: every query is bounded"
    assert {r for sql in sqls for r in re.findall(r"\bfrom\s+(srv_\w+)", sql)} == {
        "srv_game_team", "srv_game"}


def test_one_sections_failure_does_not_cascade_into_the_other():
    """🚨 A174 (cfdb-main-R-1708). AC-8.2's rule — *a blocked TAB does not block the PAGE* —
    at SECTION grain, and §6.1's calibration step is what found it.

    📊 `states.section` CATCHES a raise and draws a card, so when the completed query failed,
    `played` was never bound — and the upcoming section's own `played.empty` check then raised
    `UnboundLocalError` and drew a SECOND card. **One section's failure corrupted the other.**

    ⚠️ **IT CANNOT APPEAR IN A HEALTHY RENDER**, which is why no ordinary test would have seen
    it: the calibration broke the first query deliberately and the cascade showed up as 2 error
    cards where 1 was expected. **A counter that is only ever checked at zero cannot tell you
    it is counting the wrong thing.**
    """
    import importlib
    import pandas as pd
    # ⚠️ `allow_error_state=True` BECAUSE THIS TEST IS ABOUT THE CARD. It deliberately fails
    # one section, so exactly one card is the PASSING state — the harness's strict default is
    # right everywhere else and would refuse this render on sight.
    with render_harness.streamlit_stubbed(allow_error_state=True) as (_st, captured, _charts):
        team = importlib.reload(importlib.import_module("views.team"))

        def fake(sql, params=None):
            if "from srv_game_team" in sql:
                raise RuntimeError("A174: the completed section's query fails")
            return pd.DataFrame([_upcoming()])

        team.query = fake
        team._schedule_tab(2026, "a-team", "A Team")
        html = "\n".join(captured)

    assert html.count("cfdb-error") == 1, (
        f"one failing section must draw ONE card; got {html.count('cfdb-error')} — the "
        f"failure is cascading into the other section")
    # And the healthy section still renders.
    assert "Upcoming" in html, "the surviving section must still draw"
