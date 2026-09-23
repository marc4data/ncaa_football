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
    gap = re.search(r"gap:([\d.]+rem)", rule(".cfdb-card-metrics {"))
    assert gap, "the metric block declares no gap"
    assert _px(gap.group(1)) >= 8, (
        f"{_px(gap.group(1))}px between metrics is the compression Marc is pointing at")


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
    assert TODAY.count("Bars under the first number") == 3, (
        "each of the three boards states its own scale")
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
    grid = TODAY[TODAY.index("def _player_card_grid("):]
    grid = grid[:grid.index("\ndef ")]
    assert "cfdb-cardcol-metrics" in grid
    assert "metric_types or ([stat_label] if stat_label else [])" in grid, (
        "a single-stat board hoists its one label; a three-metric board hoists its three")


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
    out = today._player_card(row, "yards", ("YDS", "TD", "INT"), spark_top=500.0)
    assert "cfdb-card" in out and "cfdb-card-spark" in out
    assert "cfdb-card-unit" not in out
