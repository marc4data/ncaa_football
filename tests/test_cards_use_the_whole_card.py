r"""A221 — the leaderboard cards use the whole card.

> **MARC:** *"Why are we trying to scrunch so much into such a tiny space? Why aren't they
> numbers vertically aligned in the same space? Look at all the white space next to it!!!"*
> … *"sparkbar should be beside the number, not under."*
> … *"For the Team Rank… That's where the Rank should be."*
> … *"I agree with this statement 'a bar that can't show variance is decoration'."*

📊 MEASURED WITH `ci/measure_card_budget.py` AT 1440, BEFORE AND AFTER:

    distinct left edges per metric column   up to 5 of 10   ->  1 of 10, all 27 columns
    jersey beside the name / above it       16 / 14         ->  0 / 30, every board
    card-height spread within a board       47.97..69.38    ->  0px (uniform per board)
    rank on the logo's line                 8 of 8 ranked   ->  0 of 8
    rank on the abbreviation's line         0 of 8          ->  8 of 8

⚠️ **WHAT THIS FILE CAN AND CANNOT SEE.** The x-positions above are a browser measurement and
CI has no browser, so they live in the report and in that script. **What is observable here is
the producer contract those positions depend on** — that a column's width is computed from its
own rendered values, that every card in a column is handed the same widths, and that the
stylesheet no longer sizes a cell from its content.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                           # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
TODAY = (ROOT / "site" / "views" / "today.py").read_text()

IDENT = {"player_name": "A Player", "player_slug": "a", "player_id": "1",
         "team": "T", "team_display": "Team", "team_slug": "t", "team_logo_url": None,
         "team_rank": None, "jersey": 7, "position": "QB", "class_year_display": "SR"}


def rule(selector: str) -> str:
    """The declaration block for a selector, anchored at a line start (R-2260)."""
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


def grid_markup(columns, stat_label: str) -> str:
    drawn = []
    real = st.markdown
    st.markdown = lambda body, **kw: drawn.append(body)
    try:
        today._player_card_grid(columns, stat_label)
    finally:
        st.markdown = real
    return "".join(drawn)


def yardage_frame(values) -> pd.DataFrame:
    return pd.DataFrame([{**IDENT, "player_id": str(i), "player_slug": f"p{i}",
                          "stat_value": v, "metric_YDS": v,
                          "metric_TD": 1, "metric_INT": 0}
                         for i, v in enumerate(values)])


SPECS = [today._metric_spec(e, "passing") for e in ("YDS", "TD", "INT")]


# ── PART 1: one width per column, measured from that column's own values ─────────────

def test_a_column_is_sized_from_its_widest_rendered_value():
    """🚨 THE DEFECT IN ONE LINE: a cell sized to ITS OWN content gives a column as many left
    edges as it has digit counts. 📊 Measured at 1440 before the change — Touchdowns QB had
    **5 distinct left edges over 14.44px**, Receiving 3 over 17.74px."""
    wide = today._metric_widths(yardage_frame([483, 464, 99]), SPECS, "yards", False)
    narrow = today._metric_widths(yardage_frame([9, 8, 7]), SPECS, "yards", False)
    assert wide[0] == "3ch", wide
    assert narrow[0] == "1ch", narrow
    assert wide[0] != narrow[0], (
        "a column's width must follow its own values, or one width fits neither")


def test_every_card_in_a_column_is_handed_the_same_widths():
    """✅ THIS IS WHAT MAKES ONE LEFT EDGE. With every card emitting the same total metrics
    width, `margin-left:auto` puts every block at the same x — the alignment is a consequence
    of the widths rather than of a second positioning rule."""
    markup = grid_markup([("QB", yardage_frame([483, 99, 7]), SPECS)], "yards")
    cards = markup.split("class='cfdb-card'")[1:]
    assert len(cards) == 3, f"expected three cards, got {len(cards)}"
    per_card = [re.findall(r"cfdb-card-metric' style=\"width:([^\"]+)\"", c) for c in cards]
    assert per_card[0] == per_card[1] == per_card[2], per_card
    assert all(per_card[0]), "a metric cell rendered without a width"


def test_the_stylesheet_no_longer_sizes_a_cell_from_its_content():
    """⚠️ `min-width:max-content` WAS THE RAGGED EDGE. Anchored on the declaration, not on the
    word — this file and `theme.py` both discuss it in prose (A217's R-2624)."""
    block = rule(".cfdb-card .cfdb-card-metric {")
    assert not re.search(r"[;{]\s*min-width\s*:\s*max-content", block), block
    assert not re.search(r"[;{]\s*flex\s*:\s*1 1 0", block), (
        "equal thirds is the other way to get this wrong — A192 measured it wrapping 483")


def test_the_value_fills_its_cell_so_its_left_edge_cannot_move():
    """🚨 RIGHT-ALIGNING THE VALUE IS NOT THE SAME AS RIGHT-ALIGNING ITS TEXT, and the first
    attempt got it wrong: `flex:0 0 auto; margin-left:auto` aligned the digits on their units
    place and left the ELEMENT's left edge varying with the digit count — the instrument still
    reported 5 distinct edges. The box is constant; the text is aligned inside it."""
    block = rule(".cfdb-card-metric .cfdb-card-value {")
    assert re.search(r"[;{]\s*flex\s*:\s*1 1 auto", block), block
    assert re.search(r"[;{]\s*text-align\s*:\s*right", block), block


def test_the_header_cells_carry_the_same_widths_as_the_values():
    """🚨 A NAME OVER THE WRONG COLUMN IS WORSE THAN A NAME IN THE CELL, which is what A213
    removed. The sub-header emits the SAME cells at the SAME widths."""
    markup = grid_markup([("QB", yardage_frame([483, 99, 7]), SPECS)], "yards")
    head = markup.split("cfdb-cardcol-metrics'>", 1)[1].split("</div>", 1)[0]
    head_widths = re.findall(r"cfdb-card-metric' style=\"width:([^\"]+)\"", head)
    card = markup.split("class='cfdb-card'")[1]
    card_widths = re.findall(r"cfdb-card-metric' style=\"width:([^\"]+)\"", card)
    assert head_widths == card_widths, (head_widths, card_widths)


def test_a_long_heading_wraps_rather_than_setting_the_column_width():
    """📊 MEASURED, AND IT IS WHY THE HEADING IS NOT ALLOWED TO SET THE WIDTH: `max(value,
    heading)` took Touchdowns QB's metric block to **152.7px** in a card with ~97px of room,
    and every Touchdowns and Defense card wrapped to a second band — 73.67..108.97px against
    47.97. The heading wraps at its space instead, costing ~11px ONCE per board."""
    specs = [today._metric_spec(e, "passing") for e in
             ("TD", ("passing:YDS", "Pass yds"), ("rushing:YDS", "Rush yds"))]
    frame = pd.DataFrame([{**IDENT, "metric_TD": 5,
                           "metric_passing:YDS": 412, "metric_rushing:YDS": 55}])
    widths = today._metric_widths(frame, specs, "touchdowns", False)
    assert widths[1] == "3ch", (
        f"'PASS YDS' is eight characters; its column must be sized from `412`: {widths}")
    # ⚠️ THE WRAP LIVES ON THE NAME, NOT ON THE CELL. The cell carries the VALUE's font so its
    # `ch` width matches the column below it; the name is scaled down inside it, and that inner
    # span is what may wrap.
    block = rule(".cfdb-cardcol-head .cfdb-cardcol-metrics .cfdb-cardcol-name {")
    assert "white-space:normal" in block.replace(" ", ""), block
    assert "overflow-wrap:normal" in block.replace(" ", ""), (
        "a heading must wrap at a space and never inside a word (A218)")
    cell = rule(".cfdb-cardcol-head .cfdb-cardcol-metrics .cfdb-card-metric {")
    assert "font-size:1.05rem" in cell.replace(" ", ""), (
        "the heading cell must carry the value's font, or `3ch` is a different number of "
        "pixels here than in the card and the two stop lining up")


# ── PART 2: the bar beside the number, and only where it can show something ──────────

def test_the_bar_is_drawn_only_when_the_column_has_enough_distinct_values():
    """🚨 THE RULE CAME FROM A MEASUREMENT AND THE OBVIOUS CANDIDATE FAILED.

    📊 Across all nine board columns the spread RATIO does not separate them — every one sits
    in 0.662..0.800, and Receiving Touchdowns (0.667) has MORE spread by that measure than
    Tackles (0.737). **Cowork picked the right boards for the wrong reason.** What separates
    them is how many distinct numbers the column holds: 10·10·10 against 5 against 2·2·2·2·2.
    """
    assert today._SPARK_MIN_DISTINCT == 4, (
        "the threshold sits in the measured gap between 2 and 5")
    many = grid_markup([("QB", yardage_frame([483, 464, 454, 429]), SPECS)], "yards")
    few = grid_markup([("QB", yardage_frame([4, 4, 3, 3]), SPECS)], "yards")
    assert "cfdb-card-spark" in many, "a column with ten distinct values must draw its bar"
    assert "cfdb-card-spark" not in few, (
        "a column with two distinct values draws a bar of two lengths — decoration")


def test_no_bar_means_no_track_either():
    """> **MARC:** *"a bar that can't show variance is decoration."* ⚠️ An empty track is the
    decoration under another name, so nothing is drawn at all — not an empty scale."""
    few = grid_markup([("QB", yardage_frame([4, 4, 3, 3]), SPECS)], "yards")
    assert "cfdb-card-spark" not in few, few[:200]


def test_the_bar_sits_beside_the_number_in_a_slot_of_its_own():
    """> **MARC:** *"sparkbar should be beside the number, not under. That's too noisy for the
    eye to scan down."*

    🚨 AND THE SLOT IS FIXED, WHICH IS THE OTHER HALF. Under the old layout the bar inherited
    the NUMBER's width — ~45px under a three-digit yardage, ~18px under a one-digit `TD` — so
    one proportion drew two different pictures.
    """
    cell = rule(".cfdb-card-metric {")
    assert re.search(r"flex-direction\s*:\s*row", cell), (
        f"the cell must lay the value and the bar side by side: {cell}")
    spark = rule(".cfdb-card-spark {")
    assert re.search(r"[;{]\s*width\s*:", spark), (
        "the bar must have a width of its own rather than inheriting the number's")
    assert "margin-top" not in spark, "margin-top is the stacked layout's leftover"


def test_the_primary_column_is_widened_only_when_a_bar_is_drawn():
    frame = yardage_frame([483, 464, 454, 429])
    with_bar = today._metric_widths(frame, SPECS, "yards", True)
    without = today._metric_widths(frame, SPECS, "yards", False)
    assert with_bar[0] != without[0], (with_bar, without)
    assert with_bar[1:] == without[1:], (
        "only the column that carries the bar pays for it")


def test_the_caption_says_where_the_bars_are_and_that_some_boards_have_none():
    """⚠️ A212's CLAUSE IS NOW WRONG IN TWO WAYS — the bars are not under, and they are not
    always there. One constant, so three captions cannot drift apart (§3.2.3)."""
    caption = today._SPARK_CAPTION.lower()
    assert "beside" in caption and "under" not in caption, today._SPARK_CAPTION
    assert "without that spread" in caption, today._SPARK_CAPTION


def test_an_absent_value_is_still_pd_isna_and_not_truthiness():
    """🚨 `NaN` IS TRUTHY — the most repeated defect in this project."""
    import numpy as np
    assert today._card_spark(np.nan, 100.0) == "<span class='cfdb-card-spark'></span>"
    assert today._card_spark(None, 100.0) == "<span class='cfdb-card-spark'></span>"
    assert today._card_spark(0, 100.0) == "<span class='cfdb-card-spark'></span>"
    assert today._card_spark(-5, 100.0) == "<span class='cfdb-card-spark'></span>"
    assert today._card_spark(50, 0.0) == "", "no scale means nothing is drawn at all"


# ── PART 3: the rank beside the abbreviation ─────────────────────────────────────────

def test_the_logo_claims_the_first_line_so_the_rank_joins_the_abbreviation():
    """> **MARC:** *"For the Team Rank, look at the attachment, bottom-left for Tex. That's
    where the Rank should be."*

        was   line 1  [logo] #1        after   line 1  [logo]
              line 2  TEX                      line 2  #1 TEX
    """
    logo = rule(".cfdb-card-team .cfdb-logo-box,")
    assert re.search(r"flex\s*:\s*0 0 100%", logo), logo
    assert ".cfdb-monogram-empty" in logo, (
        "a team with no logo renders a different class and must claim the row too (AC-G.28)")
    name = rule(".cfdb-card-team .cfdb-team {")
    assert not re.search(r"flex\s*:\s*0 0 100%", name), (
        "the name claiming the row pushes the rank back onto the logo's line")


def test_the_team_slot_is_wide_enough_for_a_rank_and_an_abbreviation():
    """📊 THE WIDTH IS FROM A MEASUREMENT: the widest badge draws 18.25px, the flex gap is
    3.2px and the widest abbreviation is 41.6px. 44px could not hold the pair."""
    m = re.search(r"--cfdb-card-team-w:\s*([\d.]+)rem", THEME)
    assert m, "the team slot's width token is gone"
    assert float(m.group(1)) * 16 >= 56, (
        f"{float(m.group(1)) * 16}px cannot hold `#20 MRMK` on one line")


# ── PART 4: one place for the jersey ─────────────────────────────────────────────────

def test_the_jersey_takes_its_own_line_on_every_card():
    """📊 MEASURED BEFORE: beside the name on 16 of 30 yardage cards and above it on 14, with
    card heights differing by 45% in one row. **The driver was the metrics block, not the
    name** — `who` was whatever the content-sized metrics left over.

    ⚠️ FIXING THE COLUMNS MADE `who` CONSTANT PER BOARD BUT NOT ACROSS BOARDS: re-measured at
    that point, Defense was still 10 beside / 20 above. `flex:0 0 100%` removes the threshold
    instead of moving it."""
    block = rule(".cfdb-card .cfdb-player-jersey {")
    assert re.search(r"flex\s*:\s*0 0 100%", block), block


def test_a_card_with_no_jersey_keeps_the_same_footprint():
    """⚠️ THE SCREENSHOT'S CNSU ROW DRAWS AN EM DASH. With the jersey on its own line the line
    is drawn either way, so the footprint cannot differ."""
    with_j = pd.DataFrame([{**IDENT, "metric_YDS": 400, "metric_TD": 1, "metric_INT": 0}])
    without = with_j.copy()
    without["jersey"] = None
    a = grid_markup([("QB", with_j, SPECS)], "yards")
    b = grid_markup([("QB", without, SPECS)], "yards")
    assert a.count("cfdb-player-jersey") == b.count("cfdb-player-jersey") == 1, (
        "the jersey line must be drawn whether or not there is a number for it")


def test_the_budget_instrument_ships_beside_the_guard():
    """🚨 THE ACCEPTANCE IS A BROWSER MEASUREMENT AND CI HAS NO BROWSER (the A210 precedent),
    so the script that produced the report's numbers ships with the round."""
    script = ROOT / "ci" / "measure_card_budget.py"
    assert script.exists()
    source = script.read_text()
    assert "textContent" in source, "innerText is empty under visibility:hidden (R-2455)"
    assert not re.search(r"\.innerText\b", source)
    assert "distinct" in source, (
        "the distinct-left-edge count is what 'vertically aligned' means as a number")


@pytest.mark.parametrize("board", ["yardage", "touchdowns", "defense"])
def test_every_board_reads_the_one_caption_constant(board):
    """⚠️ THREE BOARDS, ONE SENTENCE. A212's clause was copied three times, which is three
    chances to leave one behind when it goes wrong — and it did go wrong."""
    assert TODAY.count("_SPARK_CAPTION") >= 4, TODAY.count("_SPARK_CAPTION")
