r"""A212 — the player cards use the room they have.

> **MARC, v14:** *"At 3 columns wide, we have more than enough real estate in each of the
> player cards… Overall - poor use of the real estate."*

📊 THE CARD'S BUDGET AT 1440, MEASURED BEFORE AND AFTER (board 0, Player yardage):

    before   286.7px = 14.4 padding + 44 team + 148.5 who + 64 metrics, gap 4px
    after    286.7px = 14.4 padding + 44 team + 143   who + 63.5 metrics, gap 9.6px

⚠️ **PART 1 IS NOT IN THIS FILE, AND THAT IS DELIBERATE.** The ranked-team wrap is real — 12 of
150 cards, three line bands against an unranked card's two — but widening the slot from 44 to
50px did not change it, so the cause is not width and no fix shipped. The report carries the
disproof; a test would be asserting a fix that does not exist.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                       # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
TODAY = (ROOT / "site" / "views" / "today.py").read_text()


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START (R-2260)."""
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


def _px(value: str) -> float:
    """A rem or px declaration as pixels, at the site's measured 16px root."""
    value = value.strip()
    return float(value[:-3]) * 16 if value.endswith("rem") else float(value[:-2])


# ── PART 2: the metrics stop being compressed ─────────────────────────────────────────

def test_the_metrics_have_real_padding_between_them():
    """> **MARC:** *"The metrics are too compressed on the right side. Spread them out, give
    > them some padding in between."*

    📊 The gap measured **4px** before and **9.6px** after, in a card 286.7px wide whose `who`
    slot had grown 36.5px past its own floor — so the metrics were the one slot not taking a
    share.
    """
    # 🚨 A221 RE-AIMED THIS, AND THE REASON IS THE ROUND'S WHOLE POINT. A212 relieved the
    # compression by widening the GAP to .6rem, because the cells were content-sized and could
    # not be widened. **A221 gives each cell a measured width instead**, so the room is in the
    # cells and the gap comes back down to .3rem — 2 x 9.6px the numbers can use.
    #
    # ⚠️ ASSERTING `gap >= 8` NOW WOULD PIN THE WORKAROUND AND FORBID THE FIX. What survives is
    # the claim underneath it: **the metric block must not be compressed**, which is now the
    # cells carrying their own width rather than the gap standing in for it.
    gap = re.search(r"gap:([\d.]+rem)", rule(".cfdb-card-metrics {"))
    assert gap, "the metric block declares no gap"
    assert _px(gap.group(1)) > 0, "the metrics must not touch"
    assert "_metric_widths" in TODAY, (
        "the cells no longer get a measured width — the compression is back")
    assert re.search(r"style=\"width:\{metric_widths\[index\]\}\"", TODAY), (
        "a metric cell must carry the width its column was measured at")


# ── PART 3: the sparkbar ──────────────────────────────────────────────────────────────

def test_the_spark_draws_its_track_for_every_state():
    """⚠️ A ZERO, A MISSING VALUE AND A NEGATIVE ALL HAVE TO DRAW SOMETHING, and `pd.isna`
    rather than truthiness because **`NaN` is truthy** — this project's most repeated defect.

    ✅ All three draw the TRACK and no fill, so an absent bar reads as an empty scale rather
    than as a missing element (AC-G.11).
    """
    for value in (None, float("nan"), 0, -5):
        out = today._card_spark(value, 100.0)
        assert "cfdb-card-spark" in out, value
        assert "<i" not in out, f"{value!r} must draw no fill"
    # a real value fills proportionally
    out = today._card_spark(50, 100.0)
    assert "<i style='width:50.0%'" in out, out
    # and it is clamped, so a bar can never run past its track
    assert "width:100.0%" in today._card_spark(500, 100.0)


def test_no_spark_at_all_when_there_is_no_scale():
    """⚠️ A DENOMINATOR OF ZERO IS NOT A FULL BAR. An empty or all-null column has no maximum,
    and the honest drawing is nothing — not a track implying a scale that does not exist."""
    assert today._card_spark(10, 0.0) == ""
    assert today._card_spark(10, None) == ""


def test_the_spark_is_scaled_per_column_and_the_page_says_so():
    """🚨 A BAR WITH NO STATED BASELINE IS DECORATION. The scale is the column being shown —
    not the season, not all of FBS — and every board that draws one says so in its caption."""
    # 🚨 A221 RE-AIMED THIS AT THE CONSTANT, AND THE OLD FORM WOULD NOW BE WRONG TWICE OVER.
    # A212's clause said the bars are UNDER the first number and that every column has one;
    # after A221 they are BESIDE it and a column without spread has none. **Counting the old
    # sentence three times would pin a sentence that is now false** — and counting the NEW one
    # three times would forbid the fix that put it in one place, which is what stops three
    # captions drifting apart (§3.2.3).
    # ⚠️ ON THE RENDERED CAPTIONS, NOT ON THE FILE (A217's R-2624). The constant's own comment
    # QUOTES the old clause to explain what changed, so "the string is absent from today.py"
    # is red on correct code — **this test's first draft failed exactly that way.**
    import ast as _ast
    captions = []
    for node in _ast.walk(_ast.parse(TODAY)):
        if (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)
                and node.func.attr == "caption" and node.args):
            captions.append(" ".join(
                n.value for n in _ast.walk(node.args[0])
                if isinstance(n, _ast.Constant) and isinstance(n.value, str)))
    assert not any("Bars under the first number" in c for c in captions), (
        "a caption still promises bars under the number, and in every column")
    assert TODAY.count("_SPARK_CAPTION") >= 4, (
        "one constant, read by all three boards — found "
        f"{TODAY.count('_SPARK_CAPTION')} mentions including its definition")
    caption = today._SPARK_CAPTION.lower()
    assert "beside" in caption, "the caption must say where the bar IS"
    assert "own ten" in caption, "a bar with no stated baseline is decoration"
    assert "without that spread" in caption, (
        "the caption must say that a board without spread has no bar")
    # 🚨 THE DENOMINATOR IS COMPUTED INSIDE THE PER-COLUMN LOOP, NOT ONCE FOR THE BOARD.
    # A staged break that emptied the value series left both `_SPARK_HEADROOM` and
    # `values.max()` in the source and this test PASSED — it was asserting that two strings
    # existed, not that a maximum was taken per column. Assert the LOCATION instead.
    grid = TODAY[TODAY.index("def _player_card_grid("):]
    grid = grid[:grid.index("\ndef ")]
    loop = grid[grid.index("for heading, frame, metric_types in columns:"):]
    loop = loop[:loop.index("\n    depth =")]
    assert "_SPARK_HEADROOM" in loop, "reuse A175's rule, not a second one"
    assert re.search(r"values\s*=\s*pd\.to_numeric\(frame\[primary\]", loop), (
        "the maximum must come from THIS column's own frame")
    assert "float(values.max())" in loop


# ── PART 4: the sub-headers look like sub-headers ─────────────────────────────────────

def test_the_sub_header_is_bigger_but_still_under_the_section_heading():
    """📊 MEASURED, ALL THREE LEVELS: section h3 **28px/600**, board label **16px/600**,
    sub-header **11.52px → 13.6px / 700**.

    ⚠️ A SUB-HEADER THAT OUT-RANKS ITS OWN SECTION IS WORSE THAN ONE THAT IS TOO SMALL, so the
    assertion is a ceiling as well as a floor.
    """
    block = rule(".cfdb-cardcol-head {")
    size = re.search(r"font-size:([\d.]+rem)", block)
    assert size, block
    drawn = _px(size.group(1))
    assert drawn > 11.52, f"{drawn}px is no bigger than what Marc called too small"
    assert drawn < 16, f"{drawn}px would meet or beat the 16px board label above it"
    assert "font-weight:700" in block


# ── PART 5: the metric name leaves the cells ──────────────────────────────────────────

def test_no_metric_name_is_printed_in_a_cell():
    """> **MARC:** *"we don't need to print the metric in every cell. Instead print it at the
    > sub-header level so people can read down a clean column"*

    📊 Measured on the page: units in cells went from `['CAR','INT','REC','TD','YDS']` and
    `['touchdowns']` to **[] on all three boards.**

    🚨 AND NO UNIT WAS LOST WITH THEM. Every string enumerated was a NAME — yards,
    touchdowns, interceptions, receptions, carries. Had one been `%` or `yds/att` it would
    have stayed: dropping a unit to win a clean column is a data change wearing a layout
    costume.
    """
    card = TODAY[TODAY.index("def _player_card("):]
    card = card[:card.index("\ndef _player_card_grid")]
    assert "cfdb-card-unit" not in card, (
        "the cells must carry numbers; the name belongs to the sub-header")


def test_the_names_appear_once_on_the_header_in_cell_order():
    """⚠️ THE ORDER IS THE CONTRACT — a reader matching the third number to the third name is
    right by construction, because both come from the same tuple in the same loop."""
    # 🚨 A213 (cfdb-main-R-2541) RE-AIMED THIS AT THE RENDERED HEADER. It used to assert that
    # one exact EXPRESSION appeared in the source — which is R-2624's trap in its purest form:
    # the claim is about what the header SAYS, and a source string stops matching the moment
    # the expression is reformatted, while saying nothing about the output either way.
    #
    # ⚠️ AND THE NAMES ARE NOW LABELS, NOT KEYS. `rushing:YDS` addresses a column; the header
    # must show `RUSH YDS`. Asserting the old expression could not have caught a header that
    # printed the key.
    import pandas as pd
    import streamlit as st
    drawn = []
    real = st.markdown
    st.markdown = lambda body, **kw: drawn.append(body)
    try:
        frame = pd.DataFrame([{
            "player_name": "A Player", "player_id": "1", "player_slug": "a-player",
            "team_display": "Team", "team_slug": "team", "team_logo_url": None,
            "team_rank": None, "jersey": 7, "position": "QB",
            "class_year_display": "SR", "stat_value": 3,
            "metric_TD": 3, "metric_passing:YDS": 412, "metric_rushing:YDS": 55}])
        specs = [today._metric_spec(e, "passing") for e in
                 ("TD", ("passing:YDS", "Pass yds"), ("rushing:YDS", "Rush yds"))]
        today._player_card_grid([("QB", frame, specs)], "touchdowns")
    finally:
        st.markdown = real
    header = "".join(drawn)
    # 🚨 A221 RE-AIMED THIS, AND THE NEW FORM IS THE STRONGER CLAIM. A213 hoisted the names as
    # ONE run of text — `TD · PASS YDS · RUSH YDS` — and this asserted that string. A221 puts
    # each name in its own `.cfdb-card-metric` cell at the same width as the values below it,
    # **so the names are now over their own columns by construction** and the separator is
    # gone. Asserting the joined string would forbid exactly that.
    # ⚠️ SLICED TO THE HEADING'S `</div>`, NOT TO `</span></span>`. The first draft used the
    # double close as the delimiter and it ATE THE LAST CELL'S OWN CLOSING TAG — so `RUSH YDS`
    # had no trailing `<` to match and the test reported two names where three were rendered.
    # **A green-looking two-of-three, from the delimiter rather than from the markup.**
    assert "cfdb-cardcol-metrics'>" in header, (
        f"the sub-header no longer emits a metrics block: {header[:200]}")
    block = header.split("cfdb-cardcol-metrics'>", 1)[1].split("</div>", 1)[0]
    names = re.findall(r"cfdb-cardcol-name'>([^<]+)<", block)
    assert names == ["TD", "PASS YDS", "RUSH YDS"], names
    # each name's cell carries a width, which is what puts it over its column
    widths = re.findall(r"cfdb-card-metric' style=\"width:([^\"]+)\"", block)
    assert len(widths) == len(names), (
        f"every heading cell must carry its column's width: {widths} for {names}")
    assert "rushing:YDS" not in header, (
        "the header must carry the LABEL, never the column key a reader cannot parse")


def test_a_board_with_no_cell_text_hoists_nothing():
    """⚠️ THE DEFENSIVE BOARD IS THE GROUP THAT CANNOT AND NEED NOT. Its `stat_label` is "",
    so its cells never carried a name — and its headings ALREADY name the metric: Tackles,
    Tackles for loss, Sacks. **Named and left alone**, which is what the prompt asked for."""
    grid = TODAY[TODAY.index("def _player_card_grid("):]
    grid = grid[:grid.index("\ndef ")]
    assert 'if stat_label else []' in grid, "an empty label must hoist nothing"
    assert '_player_card_grid(defence, "")' in TODAY


def test_the_card_still_renders_end_to_end():
    """⚠️ FIVE PARTS TOUCHED ONE FUNCTION; a syntax-clean card that raises on a real row is a
    handled error card, which looks considered (A141's class)."""
    row = pd.Series({"metric_YDS": 412, "metric_TD": 3, "metric_INT": 1,
                     "stat_value": 412, "team_abbreviation": "ND",
                     "team_display": "Notre Dame", "team_slug": "notre-dame",
                     "team_logo_url": None, "team_rank": 3.0,
                     "player_name": "A Player", "position": "QB",
                     "class_year_display": "SR", "jersey": 9})
    # ⚠️ A213: SPECS, NOT BARE TYPES — and the values are asserted, because with bare strings
    # this call still RENDERS (every cell reads an absent column and draws an em dash) and the
    # old assertions could not tell that apart from working. A test that passes on three
    # em dashes is not testing the card.
    specs = [today._metric_spec(e, "passing") for e in ("YDS", "TD", "INT")]
    out = today._player_card(row, "yards", specs, spark_top=500.0)
    assert "cfdb-card" in out and "cfdb-card-spark" in out
    assert "cfdb-card-unit" not in out
    assert re.findall(r"cfdb-card-value'>([^<]+)<", out) == ["412", "3", "1"]
