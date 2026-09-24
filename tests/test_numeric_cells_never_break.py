"""A217 — a number is one token, and the page must never break it in half.

📊 SHIPPED, AND READ OFF THE PIXELS OF A211's OWN `A211_after_schedule_1440_light.png`:
Schedule's O/U column rendered `56.0` as `56.` / `0`, `52.5` as `52.` / `5`, `71.5` as `71.` /
`5`, and the SPREAD header as `SPREA` / `D`. At 1440, sidebar open, on the page Marc reads most.

🚨 THE CAUSE IS STREAMLIT'S, NOT OURS, WHICH IS WHY NOTHING IN `theme.py` MENTIONED IT. The
computed `overflow-wrap` on every `.cfdb-table` cell was **break-word** — measured in the
browser — and this stylesheet contains no `overflow-wrap`, `word-break` or `word-wrap` rule at
all. `break-word` licenses a break INSIDE a token the moment the box is a hair too narrow, and
O/U is a hair too narrow: 52.4px drawn against 52.3px of content.

📊 AFTER, measured on Schedule, both themes:

    width  container  numeric cells wrapped  numeric cells clipped
    1440   980        0                      0
    1280   820        0                      118
    1100   640        0                      213
    1024   564        0                      266

✅ ZERO AT EVERY WIDTH, and at 1440 — Marc's width — zero clipped as well, so the fix costs
nothing where he reads. ⚠️ Below that a number is CLIPPED (`56.…`) rather than broken, which is
the trade this round took deliberately: clipped, a reader knows something is missing; split,
`51.5` reads as two numbers and the row still looks complete.

🚨 AND THE CLIPPING IS NOT FIXABLE BY WIDTHS. Schedule's ten columns need **936px** of content
and the container is **564px** at 1024. That is A208's `.cfdb-scroll` wrapper, which A208
measured Schedule as NOT having — a decision, priced in the report, not taken here.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib.table import Col                                     # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START.

    🚨 A SELECTOR IS NOT A SUBSTRING (R-2260, and three times since).
    """
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


NUMERIC_RULE = ".cfdb-table th.cfdb-num, .cfdb-table td.cfdb-num {"
VALUE_RULE = ".cfdb-table td.cfdb-num {"
ALL_CELLS_RULE = ".cfdb-table td, .cfdb-table th {"


def test_a_numeric_cell_may_not_break_inside_its_value():
    """🚨 BOTH GUARANTEES SURVIVE; A218 MOVED WHERE THEY LIVE.

    `overflow-wrap:normal` puts the token back together — it is what undoes Streamlit's
    `break-word` — and A218 promoted it from the numeric rule to EVERY cell, because `ESPN`
    was still splitting after `ESP` in a text column. `white-space:nowrap` then keeps a number
    on one line, and A218 narrowed it to `td` alone so a header may wrap rather than truncate.

    ⚠️ THE ASSERTION FOLLOWS THE ADDRESS, NOT THE OTHER WAY ROUND: what must stay true is that
    a numeric VALUE can neither break inside itself nor take a second line.
    """
    assert "overflow-wrap:normal" in rule(ALL_CELLS_RULE), (
        "without this, Streamlit's `break-word` breaks `56.0` into `56.` and `0`")
    assert "white-space:nowrap" in rule(VALUE_RULE), (
        "without this a number can still take a second line at a space or a sign")


def test_a_numeric_header_may_wrap_but_a_numeric_value_may_not():
    """🚨 A218 (cfdb-main-R-2641). THE TWO HALVES OF A COLUMN GET OPPOSITE TREATMENT.

    📊 A217 applied `nowrap` to `th.cfdb-num` and `td.cfdb-num` in one selector, and Schedule's
    header truncated to `SPRE…` at 1440 — a column nobody can name. A value truncates visibly
    and the reader knows to look elsewhere; a LABEL loses the word with nothing to recover it.
    """
    assert "white-space:nowrap" not in rule(NUMERIC_RULE), (
        "the shared numeric rule must not put nowrap on the header again")
    assert "white-space:nowrap" in rule(VALUE_RULE)
    # and the header is allowed to break its word rather than lose it
    assert "overflow-wrap:break-word" in rule(".cfdb-table th {")


def test_the_cell_clips_visibly_rather_than_overflowing():
    """⚠️ `nowrap` WITHOUT A CLIP IS A NUMBER LYING ACROSS ITS NEIGHBOUR (A210's warning).
    `.cfdb-table td` already carries `overflow:hidden` and `text-overflow:ellipsis`, so the
    honest failure is `56.…`. This asserts that pairing still exists rather than assuming it."""
    block = rule(".cfdb-table td, .cfdb-table th {")
    assert "overflow:hidden" in block
    assert "text-overflow:ellipsis" in block


def test_the_fix_does_not_escape_to_text_columns():
    """🚨 A TEAM NAME ON TWO LINES IS A LAYOUT; A NUMBER ON TWO LINES IS A LIE.

    📊 Schedule's Away and Home cells wrap 71/71 at 1440 and that is CORRECT — name over
    record. If this rule reached them the names would clip instead, which is a regression
    dressed as a fix.
    """
    # the rule names `.cfdb-num` on both sides; it must not be a bare cell selector
    assert re.search(r"^\.cfdb-table th\.cfdb-num, \.cfdb-table td\.cfdb-num \{", THEME, re.M)
    # and no rule in the stylesheet puts nowrap on every table cell
    blanket = re.search(r"^\.cfdb-table (td|th)[^.{]*\{[^}]*white-space:nowrap", THEME, re.M)
    assert not blanket, f"nowrap escaped to every cell: {blanket.group(0)[:80]!r}"


def test_one_class_covers_every_numeric_column_on_the_site():
    """⚠️ THE SWEEP IS A CLASS, NOT A LIST OF PAGES. 📊 Twelve modules build a numeric column;
    `Col.css` gives all three numeric kinds the same class, so one rule reaches all of them.
    Fixing this one column at a time is how it comes back."""
    for kind in ("num", "signed", "plain"):
        assert Col("x", "X", kind).css == "cfdb-num", kind
    # and a text column must NOT get it, or the rule would reach prose
    assert Col("x", "X").css == ""
    assert Col("x", "X", "center").css == "cfdb-center"


def test_the_stylesheet_still_sets_no_break_rule_of_its_own():
    """📊 THE MEASUREMENT THAT FOUND THIS: `overflow-wrap` computed to `break-word` on every
    cell while `theme.py` contained no such rule — so the value came from Streamlit. ⚠️ If this
    file ever grows a blanket `word-break` or `overflow-wrap`, the diagnosis above stops being
    true and the next reader inherits a wrong story."""
    # 🚨 A DECLARATION, NOT THE WORD. The first draft asserted `"word-break" not in THEME` and
    # failed on THIS ROUND'S OWN COMMENT, which names the property to explain the diagnosis.
    # In a file that documents this densely, "the string is absent" is almost never the
    # assertion you want — §2.2.1c.1's lesson, arriving inside the test again.
    declarations = re.findall(r"[;{]\s*(word-break|word-wrap|overflow-wrap)\s*:", THEME)
    # ⚠️ A218 ADDED ONE: `normal` on every cell, and `break-word` back on the header alone.
    # `word-break` and `word-wrap` must still be absent — the diagnosis depends on it.
    assert set(declarations) == {"overflow-wrap"}, (
        f"a break-related declaration that is not overflow-wrap appeared: {declarations}")
    # ⚠️ A221 ADDED A THIRD, AND THE COUNT IS RE-AIMED RATHER THAN RAISED. The bound exists so
    # a blanket break rule cannot creep in unnoticed; a THIRD site that is `normal` is the same
    # rule being applied again, not the diagnosis being undone. So the check now asserts what
    # each declaration SAYS: only the table header may re-enable `break-word`, and everything
    # else must be `normal`.
    #
    # 📊 A221's third is the leaderboard sub-header's metric cells. They carry hoisted names
    # like `PASS YDS`, they are not table cells, and Streamlit's inherited `break-word` would
    # split one mid-word — which is the very defect A218 shipped this rule to end.
    values = re.findall(r"[;{]\s*overflow-wrap\s*:\s*([a-z-]+)", THEME)
    assert sorted(values) == ["break-word", "normal", "normal"], (
        f"overflow-wrap is set to {values} — only the table header may re-enable break-word, "
        f"and every other site must be normal")


def test_the_measurement_script_exists_and_names_its_instrument():
    """🚨 THE ACCEPTANCE IS A BROWSER COUNT AND CI HAS NO BROWSER, so the reproducible
    instrument ships beside the guard — the A210 precedent. ⚠️ It must NOT use `scrollWidth`:
    on a `table-cell` that reported 0 cells short at 1440 while the pixels showed `56.` / `0`."""
    script = (ROOT / "ci" / "measure_cell_wrap.py")
    assert script.exists(), "the instrument that produced the report's numbers must ship"
    source = script.read_text()
    assert "textContent" in source
    # ⚠️ THE PROPERTY ACCESS, not the word: the script's own docstring explains why it avoids
    # `innerText`, so the bare word is present on purpose.
    assert not re.search(r"\.innerText\b", source), (
        "innerText is empty under visibility:hidden (R-2455)")
