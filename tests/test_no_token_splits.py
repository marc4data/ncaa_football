"""A218 — nothing splits a token in half, and a column label keeps its word.

🚨 A217 FIXED A COLUMN KIND. THE DEFECT IS A KIND OF BREAK. A217's prompt framed it as *a
header may wrap; a value may not* and pointed the fix at `.cfdb-num`; measured after it
shipped, Schedule's TV column still drew `ESPN` as `ESP` / `N` and `CBSSN` as `CBSS` / `N`.
**A network name is one token, exactly like a number.**

📊 SCHEDULE's BIG TABLE, one instrument, before and after:

    width   td token-splits        th labels truncated
            before -> after        before -> after
    1440    10     -> 0            1      -> 0
    1280    14     -> 0            2      -> 0
    1100    45     -> 0            2      -> 0
    1024    45     -> 0            2      -> 0

⚠️ AND THE COST, STATED: a token that used to break now CLIPS. Schedule's `td` clip count rose
70 -> 80 at 1440 and 337 -> 382 at 1024, which is the same cells failing a better way — A217's
rule that a reader can see a truncation and cannot see a lie. Text cells that wrap at a SPACE
did not rise: 1 -> 1 at 1440, 178 -> 178 at 1024.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START (R-2260)."""
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


ALL_CELLS = ".cfdb-table td, .cfdb-table th {"
HEADER = ".cfdb-table th {"
VALUE = ".cfdb-table td.cfdb-num {"
SHARED_NUM = ".cfdb-table th.cfdb-num, .cfdb-table td.cfdb-num {"


# ── PART 1: no mid-token break, in any cell ───────────────────────────────────────────

def test_no_cell_may_break_inside_a_token():
    """🚨 EVERY CELL, NOT JUST THE NUMERIC ONES. Streamlit's stylesheet sets
    `overflow-wrap:break-word` on these cells; this is what overrides it, and A217 scoped the
    override to `.cfdb-num` so text columns kept splitting."""
    assert "overflow-wrap:normal" in rule(ALL_CELLS), (
        "a text cell will split `ESPN` into `ESP` and `N` without this")


def test_the_override_is_not_scoped_to_numeric_columns_any_more():
    """⚠️ THE REGRESSION THIS ROUND EXISTS TO PREVENT: putting `normal` back on `.cfdb-num`
    alone, which reads as tidier and leaves every text column broken."""
    assert "overflow-wrap" not in rule(SHARED_NUM), (
        "the numeric rule must not be where the token fix lives — it belongs on every cell")


# ── PART 2: a label keeps its word ────────────────────────────────────────────────────

def test_a_header_breaks_its_word_rather_than_losing_it():
    """> A217 shipped `SPRE…` at 1440 and `SPR…` at 1280 — a column nobody can name.

    🚨 FOR A LABEL THE TRADE INVERTS. A truncated number is visibly incomplete and the reader
    knows to look elsewhere; a truncated LABEL loses the word with nothing to recover it from.
    `SPREA` / `D` is ugly; `SPRE…` is unreadable. **Complete beats tidy in the header row.**
    """
    assert "overflow-wrap:break-word" in rule(HEADER)
    # 📊 and it measurably worked: Schedule's truncated-label count went 1/2/2/2 -> 0/0/0/0
    # across 1440/1280/1100/1024.


def test_the_value_keeps_nowrap_and_the_header_gives_it_up():
    """⚠️ A NUMBER ON TWO LINES IS A LIE; A LABEL ON TWO LINES IS MERELY UGLY. A217 applied
    `nowrap` to `th` and `td` through one selector, which is what truncated the label."""
    assert "white-space:nowrap" in rule(VALUE)
    assert "white-space:nowrap" not in rule(SHARED_NUM), (
        "nowrap on the shared selector truncates the header again")
    assert "white-space:nowrap" not in rule(HEADER), (
        "a header must be free to take a second line")


def test_the_header_licence_cannot_reach_a_value():
    """🚨 `break-word` ON A `td` WOULD UNDO PART 1 ENTIRELY. The rule that grants it names
    `th` and nothing else — asserted on the SELECTOR, because a `td` inheriting it is exactly
    the defect A217 and A218 have now each spent a round on."""
    m = re.search(r"^(\.cfdb-table [^{\n]*)\{[^}]*overflow-wrap:break-word", THEME, re.M)
    assert m, "no rule grants break-word"
    selector = m.group(1).strip()
    assert selector == ".cfdb-table th", f"break-word must be the header's alone, got {selector!r}"
    assert " td" not in selector


def test_both_day_blocks_render_the_label_the_same_way():
    """⚠️ A PAGE THAT NAMES A COLUMN TWO WAYS IS WORSE THAN EITHER WAY.

    📊 Schedule computes ONE layout over the whole frame and hands it to every day block —
    `_dense` calls `column_layout` once — so the blocks cannot diverge by construction. This
    asserts that single call, which is the mechanism the acceptance rests on.
    """
    schedule = (ROOT / "site" / "views" / "schedule.py").read_text()
    body = schedule[schedule.index("def _dense("):]
    body = body[:body.index("\ndef ")]
    assert body.count("column_layout(") == 1, (
        "one layout for every day block, or two blocks can size a column differently")
    assert "layout=layout" in body, "the one layout must reach the render call"


# ── PART 3: the instrument counts the whole population ────────────────────────────────

def test_the_instrument_measures_headers_as_well_as_cells():
    """🚨 A217's RESULTS TABLE SAID `numeric cells clipped: 0` AT 1440 WHILE `SPREAD`'s OWN
    HEADER WAS CLIPPED AT THAT WIDTH. Both of its scripts walked `tbody tr` only.

    ⚠️ **A measurement that silently excludes half its population** is the class this project
    has paid for repeatedly, and here it excluded the header row.
    """
    source = (ROOT / "ci" / "measure_cell_wrap.py").read_text()
    # 🚨 THE CALL, NOT THE SELECTOR STRING. A staged break commented the header loop out and
    # this test PASSED, because `thead th` still appeared in the line that COLLECTS the
    # headers. Presence of a string is not evidence that anything runs it — A217's R-2624
    # again, and it is the third time this session.
    assert re.search(r"^\s*heads\.forEach\(.*look\(", source, re.M), (
        "the header row must actually be walked, not merely selected")
    assert re.search(r"^\s*table\.querySelectorAll\('tbody tr'\)\.forEach", source, re.M), (
        "the body rows must actually be walked")
    # the header and the body are reported SEPARATELY, or a clipped label hides in a total
    for key in ("thSplit", "tdSplit", "thClip", "tdClip"):
        assert key in source, key


def test_the_instrument_keeps_the_lessons_it_was_built_from():
    """⚠️ FOUR HARD-WON RULES, EACH ONE PAID FOR BY A WRONG NUMBER IN A SHIPPED REPORT."""
    source = (ROOT / "ci" / "measure_cell_wrap.py").read_text()
    # `innerText` is empty under visibility:hidden (R-2455) — the PROPERTY, not the word
    assert not re.search(r"\.innerText\b", source)
    assert "textContent" in source
    # `scrollWidth` is meaningless on a table-cell (A217's R-2622)
    assert not re.search(r"\.scrollWidth\b", source)
    # the line count comes from HEIGHT, not from a rect count (A217's R-2623)
    assert "lineH" in source


def test_the_clip_test_uses_rendered_geometry_not_a_probe():
    """📊 A probe asked how wide `☀ 76°F` would be and reported 70 clipped `Wx` cells at 1440
    for a string the browser never draws that way — the cell carries a weather glyph the probe
    cannot reproduce. The laid-out text's own rects are the honest width."""
    source = (ROOT / "ci" / "measure_cell_wrap.py").read_text()
    assert re.search(r"drawnWidth > box", source), "the clip test must use the drawn width"
    # 🚨 AND `drawnWidth` MUST COME FROM THE LAID-OUT RECTS. A staged break reassigned it to
    # `cell.scrollWidth` and this test PASSED, because it only asked that the name existed —
    # the assertion was about a variable rather than about where its value comes from.
    assign = re.search(r"const drawnWidth = ([^;]+);", source)
    assert assign, "no drawnWidth assignment"
    assert "right - left" in assign.group(1), (
        f"drawnWidth must come from the text rects, got {assign.group(1)!r}")
