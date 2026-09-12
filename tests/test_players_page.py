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
from render_harness import assert_captured, plain, render


def test_the_players_page_renders_its_default_state_without_an_error_card():
    """STRICT BY DEFAULT (R-610): `render()` refuses an Error card, so this is the guard.

    The default state — no player chosen — exercises the search panel and the page shell, which
    is every section that draws before a selection is made.
    """
    text, _charts = render("players")
    flat = plain(assert_captured(text, "Nothing to show", "the players page"))
    assert "Type at least two characters" in flat, (
        "the search prompt is the page's whole default state; if it is gone the assertion above "
        "is passing on some other empty card")


def test_the_made_attempted_cell_reads_the_rate_and_does_not_compute_it():
    """R-611. §4.2: arithmetic BETWEEN TWO COLUMNS belongs upstream.

    `srv_player_game_log.stat_made_rate` carries it; the page scales one column by 100, which is
    rendering. This pins the division out rather than trusting a comment — a `made / attempted`
    reappearing here is the defect returning.
    """
    import ast
    import pathlib

    source = pathlib.Path("site/views/players.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    value_fn = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "_value"), None)
    assert value_fn is not None, "_value() moved; this contract can no longer be checked"

    divisions = [n for n in ast.walk(value_fn)
                 if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
    assert not divisions, (
        "_value() divides again — that is arithmetic between two columns in the page, which "
        "§4.2 puts upstream. srv_player_game_log.stat_made_rate already carries it.")
    assert "stat_made_rate" in source, (
        "the page no longer reads stat_made_rate, so either the column was dropped or the "
        "division came back by another route")


# ⚠️ NO TEST HERE FOR "the page reads a column no query selects". R-623 ALREADY OWNS IT.
#
# A111 wrote one, and then its own staged break proved the duplicate was unnecessary: dropping
# `stat_made_rate` from the game-log SELECT turned `tests/test_page_reads_guard.py` red on the same
# run, because `ci/check_page_reads.py` already takes "the union of every column selected by every
# query in the module, against every column read" and fails on a column no query selects.
#
# 🚨 SO THE SECOND ONE WAS DELETED RATHER THAN KEPT. Two guards over one rule is the shape this
# project calls drift — the same reasoning that put the dataset caption in `states.section` instead
# of a second panel-to-view list beside it (R-574).
