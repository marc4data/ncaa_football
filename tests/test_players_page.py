"""The Players page, under the strict render guard. R-702 / R-611.

B092 and B094 built a guard that refuses an Error card and pointed it at nine Matchup test files
and nowhere else. This brings the Players page under it.

🚨 WHAT THIS FILE DELIBERATELY DOES NOT COVER, AND WHY — read before adding to it.

A111 was asked to render this page with a player whose plays come back EMPTY and assert the Empty
state. **That cannot be written against the harness as it stands, and the reason is the harness
rather than the page.** `site/views/players.py` builds its play filters in columns:

    left, middle, right = st.columns(3)
    down = left.selectbox("Down", ["Any", "1", "2", "3", "4"])

Measured, both ways, in A111:

    st.selectbox("Down", ["Any", ...])    -> 'Any'      <- module level, stubbed
    left.selectbox("Down", ["Any", ...])  -> None       <- COLUMN level, generic recorder

`Recorder.__getattr__` returns a recorder that records and returns None, so the page then runs
`None if down == "Any" else int(down)` and raises `TypeError: int() argument must be ... not
'NoneType'` — which `states.section` catches and draws as an Error card. Real Streamlit returns the
selected value from a column exactly as it does from `st`, so **this cannot happen on the site.**

⚠️ THE HARNESS'S OWN HEADER PREDICTED THIS CLASS at point 3: "NESTED COLUMNS ARE MODELLED, NOT
RECORDED. A generic recorder returns None ... and the page looks broken for a reason that is the
harness's." Columns making columns was modelled; columns returning WIDGET VALUES was not.

✅ `tests/render_harness.py` IS SHARED AND B094 JUST REWORKED IT, so §3 rule 3.1 applies: A111 did
not change it, and the change it needs is named in the report for Cowork to route. Once a Recorder
returns widget values the way the module-level stubs do, the empty-plays test is three lines.
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
