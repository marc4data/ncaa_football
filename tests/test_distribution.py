"""The renderer, and the one property that makes a row of sparklines mean anything.

`plot_distribution` was the reference; this is the port, split into data (dbt) and drawing
(here). Most of what follows is about the drawing being HONEST rather than pretty: a bin that
is empty must look measured rather than missing, a week with no row must reserve its width,
and the thumbnail and the panel must be the same picture at two sizes.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import distribution                       # noqa: E402


def _row(**overrides):
    """A realistic row — the shape srv_week_metric_distribution actually returns, taken from
    2025 week 9's implied-favorite distribution."""
    row = {
        "season": 2025, "season_type": "regular", "week": 9, "span": "week",
        "metric": "market_implied_favorite_points", "as_of_date": "2026-09-04",
        "bin_counts": "0,0,0,3,25,14,9,2,0,0",
        "bin_min": 0, "bin_max": 60, "bin_incr": 6.0, "bin_count": 10,
        "below_min_count": 0, "above_max_count": 0,
        "n": 53, "games_in_week": 53, "coverage_pct": 100.0,
        "games_locked": 53, "games_live": 0, "is_locked": True,
        "min_value": 18.5, "max_value": 45.0,
        "p25": 27.5, "p50": 29.8, "p75": 32.0,
        "whisker_lo": 21.3, "whisker_hi": 38.0, "outlier_count": 5,
    }
    row.update(overrides)
    return pd.Series(row)


# --- the counts cross a layer boundary as text, and that is a decision ---------------------

def test_the_bin_counts_parse_from_the_delimited_string():
    """They travel as '0,3,9,...' rather than as an array because dbt dispatches these models
    onto Postgres and Databricks, whose array types and aggregates differ, and this project
    has one portability macro layer rather than two."""
    assert distribution.parse_bin_counts("0,3,9,25,15,1,0,0,0,0") == [0, 3, 9, 25, 15, 1, 0, 0, 0, 0]
    assert distribution.parse_bin_counts(" 1 , 2 ,3 ") == [1, 2, 3]


def test_a_malformed_count_is_not_silently_a_zero():
    """A zero is a measurement — the bin was checked and held nothing. Coercing a broken
    string to zeros would draw a plausible histogram from corrupt data, which is the exact
    class of failure the null/zero rule (AC-G.32) exists to prevent."""
    assert distribution.parse_bin_counts("0,3,banana,1") == []
    assert distribution.parse_bin_counts(None) == []
    assert distribution.parse_bin_counts(float("nan")) == []
    assert distribution.parse_bin_counts("") == []


# --- the drawing ---------------------------------------------------------------------------

def test_every_bin_is_drawn_including_the_empty_ones():
    """A gap where a bin had no games is a DIFFERENT PICTURE from a short bar: it reads as the
    chart stopping rather than as the market not going there. Ten bins in, ten bars out."""
    svg = distribution.thumbnail(_row(), "Implied fav")
    assert svg.count("<rect") == 10
    # ...and the empty ones are visibly fainter, so "measured and empty" is distinguishable
    # from "measured and small" without reading the tooltip.
    opacities = {float(o) for o in re.findall(r"fill-opacity='([\d.]+)'", svg)}
    assert len(opacities) == 2, opacities


def test_a_bar_is_never_zero_pixels_tall():
    """An empty bin drawn at zero height is indistinguishable from no bin at all, which is the
    thing the test above is about — asserted on the geometry rather than on the count."""
    svg = distribution.thumbnail(_row(bin_counts="0,0,0,0,0,0,0,0,0,53"), "x")
    heights = [float(h) for h in re.findall(r"height='([\d.]+)'", svg)]
    assert min(heights) >= distribution.EMPTY_BIN_PIXELS
    assert max(heights) > min(heights), "a populated bin must still be taller than an empty one"


def test_the_median_tick_sits_on_the_bin_axis_not_on_the_observed_range():
    """THE AXIS IS WHAT MAKES TWO WEEKS COMPARABLE. Placing the tick as a fraction of the
    OBSERVED range would move the same median to a different pixel in a week with a wider
    spread, and a row of sparklines would be quietly lying."""
    width = 120
    row = _row(p50=30.0, bin_min=0, bin_max=60)
    x = distribution._value_to_x(30.0, row, width)
    assert x == pytest.approx(width / 2), "a median at the axis midpoint draws at the middle"
    # A different observed range, same median, same pixel.
    assert distribution._value_to_x(30.0, _row(min_value=1, max_value=59), width) == \
        pytest.approx(width / 2)


def test_a_value_outside_the_axis_is_not_drawn_at_the_edge():
    """Clamping would put an out-of-range median ON the boundary, where it reads as a real
    measurement at the extreme rather than as one the axis cannot show. The tails are counted
    on the row (below_min_count / above_max_count) precisely so this does not have to lie."""
    assert distribution._value_to_x(-5, _row(), 120) is None
    assert distribution._value_to_x(65, _row(), 120) is None
    assert distribution._value_to_x(None, _row(), 120) is None


# --- the empty state is a width, not an absence --------------------------------------------

def test_a_week_with_no_row_still_reserves_its_width():
    """R-141's lesson, applied. An element that appears only when populated shifts everything
    beside it the moment a week is half-priced — so the absent case draws a box of the same
    size rather than nothing."""
    empty = distribution.thumbnail(None, "TEMP")
    assert "cfdb-dist-empty" in empty
    assert "width:120px" in empty
    assert "TEMP" in empty, "the label stays, or the reader cannot tell WHICH metric is absent"
    assert "<rect" not in empty


def test_the_panel_says_so_too_rather_than_rendering_an_empty_chart():
    assert "holds no distribution" in distribution.panel(None, "O/U")


# --- one picture, two sizes -----------------------------------------------------------------

def test_the_thumbnail_and_the_panel_derive_the_same_geometry_from_the_same_row():
    """ONE RENDERER, NOT TWO. An earlier design had the thumbnail as inline SVG and the panel
    as Vega-Lite, which is two implementations of one picture — and the day they disagree the
    reader cannot tell which is lying.

    Asserted on the RENDERED OUTPUT rather than by reading the code: both must produce the
    same number of bars from the same counts, and place the median at the same fraction of
    their own width.
    """
    row = _row()
    thumb = distribution.thumbnail(row, "x", width=120)
    panel = distribution.panel(row, "x", width=420)
    assert thumb.count("<rect") == 10
    assert panel.count("<rect") == 11, "ten bars plus the box"

    def median_fraction(svg, width):
        line = re.search(r"<line x1='([\d.]+)'", svg)
        return float(line.group(1)) / width

    assert median_fraction(thumb, 120) == pytest.approx(median_fraction(panel, 420), abs=1e-6)


def test_the_panel_box_sits_inside_its_whiskers():
    """A box drawn outside its whiskers is a transposed pair of columns, and it renders as a
    plausible chart. Checked on the geometry, in pixels."""
    svg = distribution.panel(_row(), "x", width=400)
    box = re.search(r"<rect x='([\d.]+)'[^>]*width='([\d.]+)'[^>]*fill-opacity='.22'", svg)
    assert box, "the interquartile box was not drawn"
    left, box_width = float(box.group(1)), float(box.group(2))
    # The HORIZONTAL whisker line specifically — y1 == y2. The first `<line` in the document
    # is the median tick inside the histogram, which is vertical and would give lo == hi.
    whisker = next(
        (m for m in re.finditer(
            r"<line x1='([\d.]+)' y1='([\d.]+)' x2='([\d.]+)' y2='([\d.]+)'", svg)
         if m.group(2) == m.group(4)), None)
    assert whisker, "no horizontal whisker line was drawn"
    lo, hi = float(whisker.group(1)), float(whisker.group(3))
    assert lo < hi
    assert lo <= left and left + box_width <= hi


# --- the tooltip carries the denominator ----------------------------------------------------

def test_the_tooltip_always_names_how_many_games_it_measured():
    """AC-G.33, and it is worse here than anywhere: a temperature distribution over the 9
    games of a week that had weather looks identical to one over 124, and the median it
    reports is a different claim entirely."""
    text = distribution.describe(_row(n=9, games_in_week=124))
    assert "n=9 of 124 games" in text


def test_an_unlocked_week_says_it_can_still_move():
    """A mid-slate row is a MIXTURE of frozen and live numbers — Thursday's game is already
    sealed into Saturday morning's figure. A reader needs to know that before quoting it."""
    text = distribution.describe(_row(is_locked=False, games_live=7))
    assert "still to kick off" in text and "7" in text
    assert "still to kick off" not in distribution.describe(_row(is_locked=True, games_live=0))
