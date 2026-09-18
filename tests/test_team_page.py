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
            "as_of_ts": pd.Timestamp("2026-09-18")}
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
