"""The Players page, under the strict render guard. R-702 / R-611 / R-618.

B092 and B094 built a guard that refuses an Error card and pointed it at nine Matchup test files
and nowhere else. This brings the Players page under it.

⚠️ THE PLAYS SECTION COULD NOT BE TESTED HERE UNTIL B096, AND THE HISTORY IS WORTH KEEPING.
`site/views/players.py` builds its play filters in columns:

    left, middle, right = st.columns(3)
    down = left.selectbox("Down", ["Any", "1", "2", "3", "4"])

Measured, both ways, in A111 against the OLD harness:

    st.selectbox("Down", ["Any", ...])    -> 'Any'      <- module level, stubbed
    left.selectbox("Down", ["Any", ...])  -> None       <- COLUMN level, generic recorder

`Recorder.__getattr__` returned a recorder that recorded and returned None, so the page ran
`None if down == "Any" else int(down)`, raised `TypeError`, and `states.section` drew an Error card
— on a page with no defect in it. A110 filed it as a page defect, A111 disproved it by rendering a
player with 689 plays and one with zero and getting the identical card, and B096 fixed the harness:
a column now answers exactly as `st` does.

✅ SO IT CAN BE WRITTEN NOW, AND B096 WROTE IT — `test_render_harness.py`'s
`test_a_SECTION_THAT_BUILDS_CONTROLS_IN_COLUMNS_reaches_its_own_empty_state` drives this very
section and asserts the Empty state is reached.

🚨 WHICH IS WHY THIS FILE DOES NOT ASSERT THE SAME THING AGAIN. That test's claim is about the
HARNESS — that a section building controls in columns can be driven at all. The claim that belongs
HERE is about the PAGE: that the empty state, once reached, says WHICH absence it is (AC-G.11).
Two guards over one rule is the drift A111 deleted a duplicate for; a second guard over a
different rule is not.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_harness  # noqa: E402


def _drive_game_log(rows):
    """Call the real `_game_log` section with a stubbed query, the way every other panel test
    in this suite does. ⚠️ NOT `render_harness.render()` — that needs a live serving database and
    the `flake8 + pytest` job has none, which A111 learned by turning CI red once.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        players = importlib.reload(importlib.import_module("views.players"))
        players.query = lambda sql, params=None: pd.DataFrame(rows)
        players._game_log(2026, "a-player-1")
        # 🚨 R-610. An Error state is not a passing state.
        render_harness.assert_no_error_card(captured, "the players game log")
        return "\n".join(captured)


def test_an_empty_game_log_draws_the_empty_state_and_not_an_error_card():
    """🚨 THE SHAPE R-702 WAS OPENED FOR: zero rows must be an Empty state (AC-G.6), never a
    failure card, and never a zero-row table.

    ⚠️ ASSERTED ON `_game_log` RATHER THAN ON THE PLAYS SECTION, AND THE REASON IS THE HARNESS.
    `_drill_down` builds its filters with `left.selectbox(...)` on a column, and a Recorder
    returns None for that, so the page raises `int(None)` before it can reach its own empty
    state. See this module's docstring — the page is correct and the harness cannot model it.
    """
    text = _drive_game_log([])
    assert "cfdb-empty" in text, (
        "an empty game log must draw the Empty state; a zero-row table or a failure card is the "
        "defect AC-G.6 exists to prevent")
    assert "Nothing to show" in text


def test_the_made_attempted_cell_reads_the_rate_rather_than_dividing():
    """R-611, asserted on what the page DRAWS rather than only on its source."""
    text = _drive_game_log([{
        "week": 2, "stat_category": "passing", "stat_type": "C/ATT",
        "stat_made": 29, "stat_attempted": 44, "stat_made_rate": 29 / 44,
        "stat_value": None, "stat_raw": "29/44", "game_date": None,
        "opponent": "Someone", "home_away": "home", "team_points": 21,
    }])
    assert "29/44 (66%)" in text, (
        "the cell must render the pair with its rate, read from stat_made_rate")


def test_a_null_rate_renders_the_pair_without_a_percentage():
    """⚠️ AC-G.32. `stat_made_rate` is NULL when nothing was attempted, and `0/0 (0%)` would
    claim a measurement that was never taken. The pair still shows; the percentage does not."""
    text = _drive_game_log([{
        "week": 3, "stat_category": "kicking", "stat_type": "FG",
        "stat_made": 0, "stat_attempted": 2, "stat_made_rate": None,
        "stat_value": None, "stat_raw": "0/2", "game_date": None,
        "opponent": "Someone", "home_away": "away", "team_points": 10,
    }])
    assert "0/2" in text and "0/2 (" not in text, (
        "with no rate the pair renders bare; a percentage here would be invented")


def test_the_page_does_not_divide_two_columns():
    """R-611. §4.2: arithmetic BETWEEN TWO COLUMNS belongs upstream. Pinned on the source so a
    rewrite cannot quietly bring the division back."""
    import ast
    source = (Path(__file__).resolve().parents[1] / "site" / "views" / "players.py").read_text()
    value_fn = next((n for n in ast.walk(ast.parse(source))
                     if isinstance(n, ast.FunctionDef) and n.name == "_value"), None)
    assert value_fn is not None, "_value() moved; this contract can no longer be checked"
    assert not [n for n in ast.walk(value_fn)
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)], (
        "_value() divides again — srv_player_game_log.stat_made_rate already carries it")


# ⚠️ NO TEST HERE FOR "the page reads a column no query selects". R-623 ALREADY OWNS IT.
#
# A111 wrote one, and then its own staged break proved the duplicate unnecessary: dropping
# `stat_made_rate` from the game-log SELECT turned `tests/test_page_reads_guard.py` red on the
# same run, because `ci/check_page_reads.py` already takes "the union of every column selected by
# every query in the module, against every column read" and fails on a column no query selects.
#
# 🚨 SO THE SECOND ONE WAS DELETED RATHER THAN KEPT. Two guards over one rule is the shape this
# project calls drift — the same reasoning that put the dataset caption in `states.section`
# instead of a second panel-to-view list beside it (R-574).


def _drive_plays(rows):
    """Drive `_drill_down` — the section that builds its filters in columns.

    ⚠️ POSSIBLE ONLY SINCE B096. Before it, a column answered None and the page raised
    `int(None)` before reaching any state of its own. See this module's docstring.
    """
    import importlib
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        players = importlib.reload(importlib.import_module("views.players"))
        players.query = lambda sql, params=None: pd.DataFrame(rows)
        players._drill_down(2026, "a-player-1")
        render_harness.assert_no_error_card(captured, "the players plays section")
        return "\n".join(captured)


def test_the_plays_empty_state_says_which_absence_it_is():
    """🚨 AC-G.11: an absence must say WHICH absence it is, and this one is not "no plays".

    `srv_player_play`'s own header is the sentence that matters — "absence here means cfdb did not
    ask about that game, never that the player did nothing." Play attribution is collected per
    game and does not cover every game, so a page that said "this player made no plays" would be
    claiming something the data cannot support.

    ⚠️ THIS IS NOT B096's TEST RESTATED. That one asserts the Empty state is REACHED, which is a
    claim about the harness. This asserts what it SAYS, which is a claim about the page — and the
    copy is the part a reader actually gets.
    """
    text = _drive_plays([])
    assert "cfdb-empty" in text, "the section must reach its own Empty state"
    flat = render_harness.plain(text)
    assert "does not yet cover every game" in flat, (
        "the empty state must say the COVERAGE is partial. Without that sentence a reader reads "
        "'no plays' as 'this player did nothing', which srv_player_play's own header forbids.")
    assert "no plays" not in flat.lower() or "No plays match those filters" in flat, (
        "an unfiltered empty must not claim the player made no plays")
