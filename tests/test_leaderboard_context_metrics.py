r"""A213 — the leaderboards carry the numbers beside the number, and say what they are.

> **MARC, v14:** *"Touchdowns — add metrics: QB: Yards Rushing, Yards Passing / Receiving:
> Catches, Yards Receiving / Rushing: Attempts, Yards Rushing"*, *"Tackles: Tackles for Loss,
> Sacks / …"*, *"DEfense Leaders - are these totals for the week? … Did all of these players
> in FBS or play against FBS?"*, *"Can a delayed hover highlight the same player if it's in
> the other Defense categories?"*

📊 PART 0, measured on live published serving before anything was built — every figure asked
for is a column on the view the page already reads, so nothing here needed a dbt round:

    QB    Yards Passing    passing/YDS      ✅      Receiving  Catches   receiving/REC  ✅
    QB    Yards Rushing    rushing/YDS      ✅      Receiving  Rec yards receiving/YDS  ✅
    Rush  Attempts         rushing/CAR      ✅      Defense    Tackles   defensive/TOT  ✅
    Rush  Yards Rushing    rushing/YDS      ✅      Defense    TFL/Sacks defensive/…    ✅

🚨 `stat_type` IS NOT A KEY ON THIS VIEW. `YDS` is published under SEVEN categories and `TD`
under six, so the fold keys on `(stat_category, stat_type)`. **A QB's passing yards and his
rushing yards are both `YDS`**, and that is the defect these tests exist to hold shut.
"""
import ast
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                       # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()

IDENTITY = {"player_name": "A Player", "player_slug": "a-player", "player_id": "1",
            "team": "Team", "team_display": "Team", "team_slug": "team",
            "team_logo_url": None, "team_rank": None, "jersey": 7,
            "position": "QB", "class_year_display": "SR"}


def melted(*rows) -> pd.DataFrame:
    """A frame shaped like `srv_player_game_log`: one row per player x category x type."""
    return pd.DataFrame([{**IDENTITY, **r} for r in rows])


def captions_in(function: str) -> list:
    """Every `st.caption` string literal inside one function, from the AST."""
    tree = ast.parse(SOURCE)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == function)
    out = []
    for call in ast.walk(node):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr == "caption" and call.args):
            # ⚠️ A221: A CAPTION MAY BE A CONCATENATION NOW. `_SPARK_CAPTION` is one constant
            # read by three boards, so the argument is `"…" + _SPARK_CAPTION` — a BinOp, which
            # `literal_eval` refuses. **The first version returned nothing for those captions
            # and two tests failed on correct copy.** Every string literal in the expression is
            # collected instead, which is what the assertions are actually about.
            out.append(" ".join(
                node.value for node in ast.walk(call.args[0])
                if isinstance(node, ast.Constant) and isinstance(node.value, str)))
    return out


def board_metrics(variable: str) -> list:
    """The metric KEYS of the first column of the board group assigned to `variable`.

    ⚠️ READ FROM `_leaderboards`' OWN SOURCE, which is the point — a ranking assertion built
    from a tuple the test wrote asserts nothing about the page (R-768).
    """
    tree = ast.parse(SOURCE)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_leaderboards")
    assign = next(n for n in ast.walk(node)
                  if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))
    first_column = assign.value.args[-1].elts[0]
    metrics = first_column.elts[-1]
    return [e.value if isinstance(e, ast.Constant) else e.elts[0].value
            for e in metrics.elts]


def grid_markup(columns, stat_label: str) -> str:
    """`_player_card_grid`'s real output, captured from `st.markdown`."""
    drawn = []
    real = st.markdown
    st.markdown = lambda body, **kw: drawn.append(body)
    try:
        today._player_card_grid(columns, stat_label)
    finally:
        st.markdown = real
    return "".join(drawn)


# ── PART 1: a figure comes from the column it names ───────────────────────────────────

def test_a_quarterbacks_rushing_yards_come_from_the_rushing_category():
    """🚨 THE BREAK THIS EXISTS FOR: reading `YDS` without its category. Both numbers below are
    `YDS` on the same player in the same game, and only the category tells them apart.

    ⚠️ THE VALUES ARE DELIBERATELY UNEQUAL AND NEITHER IS AN IDENTITY ELEMENT (R-843) — 412
    against 55, so a fold that took the wrong row, or the first row, or the max, all differ
    from the right answer and differ from each other.
    """
    frame = melted(
        {"stat_category": "passing", "stat_type": "TD", "stat_value": 4},
        {"stat_category": "passing", "stat_type": "YDS", "stat_value": 412},
        {"stat_category": "rushing", "stat_type": "YDS", "stat_value": 55},
    )
    specs = [today._metric_spec(e, "passing") for e in
             ("TD", ("passing:YDS", "Pass yds"), ("rushing:YDS", "Rush yds"))]
    folded = today._fold_metrics(frame, specs, 10)
    assert folded["metric_passing:YDS"].iloc[0] == 412
    assert folded["metric_rushing:YDS"].iloc[0] == 55, (
        "the rushing column took a passing row — `stat_type` alone is not a key on this view")


def test_the_board_asks_the_query_for_every_category_its_metrics_name():
    """⚠️ A FOLD CANNOT RECOVER A ROW THE QUERY NEVER FETCHED. The QB touchdown board reads
    two categories, so `_boards` must widen the `WHERE` — and it must stay ONE single-table
    SELECT (§4.2.1), which is why the categories are an `IN` list and not a second query."""
    specs = [today._metric_spec(e, "passing") for e in
             ("TD", ("passing:YDS", "Pass yds"), ("rushing:YDS", "Rush yds"))]
    cats, types = today._board_query_args(specs)
    assert set(cats) == {"passing", "rushing"}, cats
    assert set(types) == {"TD", "YDS"}, types


def test_the_touchdown_board_is_ranked_by_touchdowns_not_by_the_yards_beside_them():
    """🚨 MARC'S OWN CAUTION, AND THE ONE A READER CANNOT SEE IS BROKEN. A board that prints
    412 yards beside 1 touchdown and 180 beside 5 looks ranked by yards unless it is not.

    📊 The order comes from `_player_board`'s window over the PRIMARY type only, and
    `_fold_metrics` takes the first `depth` of that order — so the test feeds the rows in
    yards order and asserts the fold keeps the query's order rather than re-sorting on the
    bigger number.
    """
    frame = pd.DataFrame([
        {**IDENTITY, "player_slug": "big-yards", "player_id": "1",
         "stat_category": "passing", "stat_type": "TD", "stat_value": 1},
        {**IDENTITY, "player_slug": "big-yards", "player_id": "1",
         "stat_category": "passing", "stat_type": "YDS", "stat_value": 412},
        {**IDENTITY, "player_slug": "many-tds", "player_id": "2",
         "stat_category": "passing", "stat_type": "TD", "stat_value": 5},
        {**IDENTITY, "player_slug": "many-tds", "player_id": "2",
         "stat_category": "passing", "stat_type": "YDS", "stat_value": 180},
    ])
    # 🚨 THE RANKING IS READ FROM THE PAGE'S OWN DECLARATION, NOT FROM A TUPLE THIS TEST
    # WROTE. The first draft built its own spec list and asserted `specs[0]` was `TD` — which
    # is R-768 exactly: *"it was testing a list the test wrote rather than the one the page
    # writes."* 📊 **The staged break proved it: moving yards to the front of the real board
    # left this test GREEN.** Only reading `_leaderboards`' own tuple can fail.
    assert board_metrics("touchdowns")[0] == "TD", (
        "the FIRST metric is the ranking — moving yards first silently re-ranks the board")
    specs = [today._metric_spec(e, "passing") for e in
             ("TD", ("passing:YDS", "Pass yds"), ("rushing:YDS", "Rush yds"))]
    folded = today._fold_metrics(frame, specs, 10)
    assert list(folded["player_slug"]) == ["big-yards", "many-tds"], (
        "the fold must preserve the query's order, which is the primary metric's")


def test_the_touchdown_caption_says_which_figure_the_order_comes_from():
    """⚠️ THE PAGE HAS TO SAY IT TOO, not only the report. A board whose ranking is invisible
    is a board a reader will read as ranked by the biggest number on it."""
    text = " ".join(captions_in("_leaderboards")).lower()
    assert "ranked by touchdowns" in text, text


# ── PART 3: the Defense board says what it is counting ────────────────────────────────

def test_the_defence_caption_states_the_period_and_the_division_scope():
    """📊 BOTH ANSWERS ARE MEASUREMENTS, taken on live published serving at week 3 of 2026:

        period   every one of 5,712 players with a `defensive`/`TOT` row has EXACTLY ONE row
                 — the view is game-grain, so each number is one game
        scope    13 of the 30 players these boards list played for an FBS team;
                 17 played neither for nor against one

    ⚠️ THIS ASSERTS USER-FACING TEXT, WHICH IS THE ONE PLACE A STRING ASSERTION IS THE RIGHT
    INSTRUMENT (R-2624 is about proving a MECHANISM with a word). Here the words ARE the
    deliverable: Marc asked for the text below the heading to answer two questions.
    """
    text = " ".join(captions_in("_leaderboards")).lower()
    assert "one game" in text, f"the period is unstated: {text}"
    assert "not filtered to fbs" in text, f"the division scope is unstated: {text}"


def test_the_caption_does_not_bake_in_a_count_that_goes_stale():
    """⚠️ §2.2.1d APPLIED TO THE PAGE'S OWN PROSE. "13 of 30" is true of week 3 and of no other
    week, and nothing on the page would ever correct it."""
    text = " ".join(captions_in("_leaderboards"))
    assert "13 of" not in text and "17 of" not in text, (
        "a measured count in a caption is a claim with no as-of stamp and no way to refresh")


# ── PART 4: the cross-board highlight ─────────────────────────────────────────────────

def _two_boards(id_a: str, id_b: str, name_a="Jayden Woods", name_b="Jayden Woods"):
    a = pd.DataFrame([{**IDENTITY, "player_id": id_a, "player_name": name_a,
                       "player_slug": "a", "stat_value": 4}])
    b = pd.DataFrame([{**IDENTITY, "player_id": id_b, "player_name": name_b,
                       "player_slug": "b", "stat_value": 3}])
    return [("Tackles", a, []), ("Sacks", b, [])]


def test_the_highlight_pairs_on_the_published_id_and_never_on_the_name():
    """🚨 TWO PLAYERS SHARE A NAME EVENTUALLY, and matching on a string is how the wrong man
    lights up. These two ARE both called `Jayden Woods` and are different people."""
    markup = grid_markup(_two_boards("101", "202"), "")
    assert "data-cfdb-player" not in markup, (
        "two different ids must not pair, however identical the names")
    assert "<style>" not in markup
    assert "Jayden Woods" not in re.findall(r"<style>(.*?)</style>", markup + "<style></style>")[0]


def test_the_same_player_on_two_boards_is_paired():
    markup = grid_markup(_two_boards("101", "101"), "")
    # ⚠️ COUNT IN THE BOARD, NOT IN THE WHOLE STRING — the rule names the id twice itself, so
    # counting the document says 4 and means nothing about how many CARDS carry it.
    board = markup[markup.index("<div class='cfdb-cardboard'>"):]
    assert board.count('data-cfdb-player="101"') == 2, board
    rules = re.findall(r"<style>(.*?)</style>", markup)
    assert rules, "a paired player must get a highlight rule"
    assert ':has(.cfdb-card[data-cfdb-player="101"]:hover)' in rules[0], rules


def test_a_player_who_appears_once_gets_no_highlight_at_all():
    """⚠️ MARC: *"It must do nothing when the player appears only once."* Structural rather
    than conditional — an unpaired card carries no attribute, so no rule can select it."""
    one = [("Tackles", pd.DataFrame([{**IDENTITY, "player_id": "101", "stat_value": 4}]), [])]
    markup = grid_markup(one, "")
    assert "data-cfdb-player" not in markup, markup
    assert "<style>" not in markup, "no pairs means no stylesheet at all"


def test_the_highlight_waits_before_it_fires_and_releases_at_once():
    """⚠️ MARC ASKED FOR A *DELAYED* HOVER. The delay is on the hover rule only: 400ms coming
    on, 0ms coming off. **A symmetric delay reads as lag rather than as intent.**"""
    markup = grid_markup(_two_boards("101", "101"), "")
    rule = re.findall(r"<style>(.*?)</style>", markup)[0]
    assert f"transition-delay:{today._HIGHLIGHT_DELAY_MS}ms" in rule, rule
    assert today._HIGHLIGHT_DELAY_MS >= 250, (
        f"{today._HIGHLIGHT_DELAY_MS}ms fires on a pointer merely crossing the board")
    base = THEME[THEME.index(".cfdb-card {"):]
    base = base[:base.index("}")]
    assert "transition:" in base, "without a transition the delay governs nothing"
    assert "transition-delay:0ms" in base, (
        "coming off the hover the base rule governs, and it must not hold the highlight on")


def test_the_highlight_needs_no_server_round_trip():
    """🚨 STREAMLIT RERUNS THE PAGE ON ANY WIDGET INTERACTION. A hover routed through Python
    would re-query and repaint on every pointer crossing — the blinking page the prompt says
    to price rather than ship. ⚠️ AND SCRIPTS ARE NOT AVAILABLE EITHER: Streamlit's sanitiser
    strips them, which R-121 established for `onerror`."""
    markup = grid_markup(_two_boards("101", "101"), "")
    assert "<script" not in markup and "onmouse" not in markup, markup
    grid = SOURCE[SOURCE.index("def _player_card_grid("):]
    grid = grid[:grid.index("\ndef ")]
    for widget in ("st.button", "st.selectbox", "st.session_state", "st.rerun"):
        assert widget not in grid, f"{widget} makes the highlight a server round-trip"
