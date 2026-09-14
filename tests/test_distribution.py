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


# --- box(), the third entry point (R-808) -----------------------------------------------

# 🚨 THE TWO WHISKER VOCABULARIES, AS FIXTURES — R-820, and the reason this file needed two.
#
# ⚠️ THIS DOCSTRING USED TO READ "a distribution row as any of the three sibling views publishes
# it" AND THAT WAS FALSE. It carries `whisker_low`, which TWO of the three publish; the week-grain
# view publishes `whisker_lo`. Meanwhile `_row()` twenty lines above — correctly labelled as the
# shape `srv_week_metric_distribution` actually returns — carried `whisker_lo` all along.
#
# 🚨 TWO FIXTURES CONTRADICTED EACH OTHER IN ONE FILE AND NOTHING COMPARED THEM, so every box test
# passed while `box()` could not draw one of the three views it promised. §6 mode 1 in its purest
# form: the fixture was doing the asserting.
#
# ✅ SO THE SHAPES ARE NAMED AND THE TESTS BELOW RUN AGAINST BOTH.
_WHISKER_SHAPES = {
    "whisker_low/high — team_week and game_team": ("whisker_low", "whisker_high"),
    "whisker_lo/hi — week (the one A125 could not draw)": ("whisker_lo", "whisker_hi"),
}


def _box_row(shape=("whisker_low", "whisker_high"), **over):
    """A distribution row in ONE of the two published whisker vocabularies.

    ⚠️ The default is the pair TWO of the three views use, so the existing tests keep testing what
    they were written to test. `shape` is how a test reaches the third.
    """
    lo_key, hi_key = shape
    row = {"n": 135, "team_games_in_week": 135,
           "p02": -3.0, "p05": 10.0, "p25": 108.0, "p50": 152.0, "p75": 232.5,
           "p95": 380.0, "p98": 410.0, "iqr": 124.5,
           lo_key: -3.0, hi_key: 418.0, "outlier_count": 2}
    row.update(over)
    return row


def _drew(svg: str) -> bool:
    """🚨 DID IT DRAW A PICTURE, OR RETURN THE PLACEHOLDER?

    ⚠️ THIS IS THE ASSERTION A125 WAS MISSING AND IT IS THE WHOLE ROUND. The empty-dash
    placeholder IS a string, so `assert svg`, `assert len(svg)` and `assert "cfdb-dist" in svg`
    all pass against a box that drew nothing. The only honest question is whether an <svg> with
    marks in it came back.
    """
    return "<svg" in svg and "<rect" in svg


def _texts(svg: str):
    """Every label the box actually emitted, with its x."""
    return [(float(x), t) for x, t in
            re.findall(r"<text x='([-\d.]+)'[^>]*>([^<]*)</text>", svg)]


def test_box_draws_marcs_five_elements():
    """Marc's specification, element by element: the box is p25-p75, the median is BOLD, the
    whiskers reach the published boundaries, the value is a blue line WITH a label, and the
    whole thing spans the width it is handed.
    """
    svg = distribution.box(_box_row(), value=180, width=300)
    assert "<rect" in svg, "the box"
    assert "stroke-width='1.8'" in svg, "the median must be BOLD — Marc said so explicitly"
    assert svg.count("<line") >= 4, "the whisker rule, two serifs, the median"
    assert distribution.VALUE_COLOR in svg, "the value marker is blue"
    assert "<polygon" in svg, "and carries a cap, so hue is not its only signal"
    assert "width='300'" in svg, "spans the width it is given"


def test_the_value_marker_survives_greyscale():
    """🚨 AC-G.22, AND THIS PANEL HAS BEEN HERE BEFORE. B102 measured green and red at 1.8 luma
    apart, separated only by Marc's diamond. A blue line on a grey box is the same trap.

    So the marker carries three signals and only one is colour: DOUBLE WEIGHT against the
    median's 1.8, a triangular CAP no other element has, and blue. This asserts the two that
    are not colour — the ones a greyscale reader is left with.
    """
    svg = distribution.box(_box_row(), value=180, width=300)
    assert "stroke-width='2.2'" in svg, "the value rule is heavier than the median's 1.8"
    assert "<polygon points=" in svg, "the cap is a shape, not a hue"


def test_labels_are_placed_rather_than_merely_emitted():
    """🚨 THE RASTER CAUGHT THIS AND THE DOM COULD NOT. The first version emitted every label at
    its own x: a value of 180 beside a median of 152 rendered as "152.080.0" — two real numbers
    overprinted into a third that is neither — and a value past the upper whisker ran off the
    edge as "450.(". Every <text> element was present and correct.

    Two claims, and the second is the one the fix turns on: THE VALUE LABEL WINS, because it is
    the number the reader came for.
    """
    svg = distribution.box(_box_row(), value=180, width=300)
    xs = sorted(x for x, _ in _texts(svg))
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    assert all(g > 14 for g in gaps), f"labels are overprinting — gaps {gaps}"
    assert any(t == "180.0" for _, t in _texts(svg)), "the value label must be the one that wins"
    assert not any(t == "152.0" for _, t in _texts(svg)), (
        "the median label collided with the value and must have been dropped, not shifted — a "
        "shifted label points at the wrong place on the axis")


def test_a_label_outside_the_frame_is_clamped_not_clipped():
    """An outlier past the whisker is the interesting case, and it was being cut off by the
    viewBox. The frame widens to include the value and the label is clamped inside it."""
    svg = distribution.box(_box_row(), value=450, width=300)
    xs = [x for x, _ in _texts(svg)]
    assert xs, "labels were drawn"
    assert max(xs) <= 300, f"a label ran past the frame at x={max(xs)}"
    assert any(t == "450.0" for _, t in _texts(svg)), "the outlier's own value must be labelled"


def test_the_tick_strategies_differ_and_none_is_invented():
    """Marc: "I want to set labels, tick mark strategy, etc." Three strategies, and each is one
    the published row can actually support — `percentiles` is the default because its ticks are
    values the row already carries."""
    row = _box_row()
    pct = distribution.box(row, value=180, width=300, ticks=distribution.TICK_PERCENTILES)
    bounds = distribution.box(row, value=180, width=300, ticks=distribution.TICK_BOUNDS)
    none = distribution.box(row, value=180, width=300, ticks=distribution.TICK_NONE)
    assert len(_texts(pct)) > len(_texts(bounds)) > len(_texts(none)), (
        "the three strategies must actually differ in how many labels they draw")
    assert len(_texts(none)) == 1, "TICK_NONE still labels the reader's own value"
    assert distribution.box(row, value=180, width=300,
                            ticks=distribution.TICK_NONE, show_value=False).count("<text") == 0


def test_box_needs_no_bin_columns_which_is_why_every_measure_is_reachable():
    """🚨 THE ROUND'S FINDING, PINNED. `thumbnail` and `panel` draw the histogram and need
    `bin_min`, `bin_incr` and `bin_counts`. A box plot is computed from the values, so the
    eighteen box-score measures could be published WITHOUT eighteen hand-set bin ranges in
    dbt_project.yml. If this ever starts needing a bin column, that trade is gone.
    """
    row = _box_row()
    for key in ("bin_min", "bin_max", "bin_incr", "bin_count", "bin_counts"):
        assert key not in row
    svg = distribution.box(row, value=180, width=300)
    assert "<rect" in svg and "<polygon" in svg, "it drew, with no bin columns present"


def test_a_row_without_percentiles_says_so_rather_than_drawing_an_empty_box():
    """AC-G.11: a week with no distribution is a different state from a week with a thin one."""
    assert "–" in distribution.box(None, width=300)
    assert "–" in distribution.box(_box_row(p25=None), value=180, width=300)


# --- R-820: box() must draw for ALL THREE siblings, not two of them ----------------------

@pytest.mark.parametrize("label,shape", list(_WHISKER_SHAPES.items()))
def test_box_draws_for_every_published_whisker_vocabulary(label, shape):
    """🚨 THE TEST A125 DID NOT WRITE, AND THE ONE THAT WOULD HAVE CAUGHT THE DEFECT.

    `box()` read `whisker_low` alone. The week-grain view publishes `whisker_lo`, so it fell
    through the guard and returned the EMPTY PLACEHOLDER — 123 characters, zero elements, titled
    "this week has no distribution for that measure".

    ⚠️ AND THAT IS THE WORST FAILURE AVAILABLE: not a crash and not a blank, but a CONFIDENT
    WRONG ABSENCE. The page would tell a reader the week has no distribution for a measure whose
    percentiles were sitting in the row it was just handed (AC-G.11).

    🚨 THE ASSERTION IS THAT IT DREW, NOT THAT A STRING CAME BACK. The placeholder is a string;
    every assertion A125 wrote passes against it.
    """
    svg = distribution.box(_box_row(shape=shape), value=180, width=448)
    assert _drew(svg), (
        f"{label}: box() returned the empty placeholder for a row that carries p25, p50, p75 and "
        f"both whiskers — the same confident wrong absence R-820 fixed")
    assert svg.count("<line") >= 4, f"{label}: the whisker rule, its serifs and the median"
    assert svg.count("<text") >= 3, f"{label}: the boundary labels and the value"


def test_both_whisker_vocabularies_draw_the_same_picture():
    """⚠️ NOT MERELY 'BOTH DRAW' — both must draw the SAME marks from the same numbers.

    A lookup that found the second vocabulary but read it into the wrong end would still draw,
    and would draw a box inside out. The two shapes carry identical values, so the element counts
    and every label must match exactly.
    """
    a = distribution.box(_box_row(shape=("whisker_low", "whisker_high")), value=180, width=448)
    b = distribution.box(_box_row(shape=("whisker_lo", "whisker_hi")), value=180, width=448)
    assert _drew(a) and _drew(b)
    for tag in ("<rect", "<line", "<text", "<polygon"):
        assert a.count(tag) == b.count(tag), f"{tag} differs between the two vocabularies"
    assert _texts(a) == _texts(b), "the two vocabularies produced different labels"


def test_a_row_mixing_the_two_vocabularies_raises_rather_than_averaging_them():
    """⚠️ `lo` and `hi` must come from the SAME view's vocabulary.

    A row answering `whisker_low` and `whisker_hi` is not an unusual spelling — it is a row no
    serving view publishes, so it can only have been built by hand. Drawing a box from two
    models' numbers would be a silent half-answer, which is how the original defect survived.

    🚨 THIS IS A PROGRAMMING ERROR, NOT A DATA CONDITION, so it raises rather than degrading.
    R-748's assert-upstream-degrade-downstream is about rows the warehouse can produce; this is
    not one.
    """
    mixed = _box_row()
    mixed["whisker_hi"] = mixed.pop("whisker_high")
    with pytest.raises(ValueError, match="without its pair"):
        distribution.box(mixed, value=180, width=448)


def test_a_row_with_no_whiskers_at_all_is_still_an_honest_absence():
    """AC-G.11 the other way: a row genuinely missing both ends has no box to draw, and the
    placeholder is correct there. The fix must not turn a real absence into a drawn box."""
    bare = _box_row()
    del bare["whisker_low"], bare["whisker_high"]
    assert not _drew(distribution.box(bare, value=180, width=448))


# --- v10: ONE CHART, TWO TEAMS ------------------------------------------------------------
#
# Marc, 2026-09-14: *"make a single box-whisker chart... Populate the single chart with data
# points for both teams. Use team color to differentiate. Would be ideal to label Away above the
# line, Home below, if possible."*
#
# 🚨 THE "IF POSSIBLE" IS THE PART THAT MATTERS MOST AND IT IS NOT OPTIONAL. Two team colours on
# one chart is AC-G.22 in its purest form — NOTHING PREVENTS TWO TEAMS BEING THE SAME RED — so
# position is the primary encoding and hue is decoration on top. Hence two breaks, not one:
# `same colour` leaves every marker drawn and merely wrong about whose is whose, and a colour
# assertion cannot see `same side` at all.

AWAY_COLOR = "light-dark(#0d5eaf, #6fb7ff)"
HOME_COLOR = "light-dark(#a6192e, #ff6b7d)"


def _polys(svg):
    """Every marker cap, as its raw points string."""
    return re.findall(r"<polygon points='([^']+)'", svg)


def _value_rules(svg):
    """Every value rule — the heavy ones, at 2.2 — as (x, y1, y2)."""
    return [(float(x), float(y1), float(y2)) for x, y1, y2 in re.findall(
        r"<line x1='([-\d.]+)' y1='([-\d.]+)' x2='[-\d.]+' y2='([-\d.]+)' "
        r"stroke='[^']*' stroke-width='2\.2'", svg)]


def _two(**kw):
    return distribution.box(_box_row(), value=180, value_below=240, width=300,
                            value_color=AWAY_COLOR, value_below_color=HOME_COLOR, **kw)


def test_the_one_value_chart_is_untouched_by_the_second_side_existing():
    """🚨 B108's CALL SITE IS ON THE LIVE SITE. `box(row, value=…)` had to keep rendering the
    identical bytes, and it does — all 14 captured shapes (widths, tick strategies, both whisker
    vocabularies, the empty states) hash the same before and after.

    These are the structural halves of that: the one-value chart reserves NO band above the box,
    so it is the same height it always was, and its marker still spans the full box rather than
    half of it.
    """
    one = distribution.box(_box_row(), value=180, width=300)
    assert "<g transform=" not in one, "a one-value chart must not be wrapped or offset"
    assert f"height='{distribution.BOX_HEIGHT + 15}'" in one, "unchanged total height"
    (_x, y1, y2), = _value_rules(one)
    assert (y1, y2) == (0.0, float(distribution.BOX_HEIGHT)), "full-height marker, as before"


def test_two_values_draw_two_markers_in_opposite_halves():
    """🚨 THE ORIENTATION IS THE ENCODING. Away's marker lives in the upper half and its cap sits
    on the top edge; home's lives in the lower half with its cap on the bottom. This is the
    assertion the `same side` break moves and the `same colour` break cannot.
    """
    svg = _two()
    rules = _value_rules(svg)
    assert len(rules) == 2, "one marker per team"
    mid = distribution.BOX_HEIGHT / 2.0
    (_ax, ay1, ay2), (_hx, hy1, hy2) = rules
    assert (ay1, ay2) == (0.0, mid), "away occupies the UPPER half"
    assert (hy1, hy2) == (mid, float(distribution.BOX_HEIGHT)), "home occupies the LOWER half"

    # The caps sit on the OUTSIDE edges and point inward at the axis, so the pair reads as a
    # mirrored set rather than two unrelated glyphs. Parsed rather than pattern-matched on a
    # hardcoded x, which would be asserting the fixture's arithmetic (R-859).
    away_cap, home_cap = [[tuple(map(float, pt.split(","))) for pt in cap.split()]
                          for cap in _polys(svg)]
    box_h = float(distribution.BOX_HEIGHT)
    assert [y for _x, y in away_cap] == [0.0, 0.0, 4.6], "away's cap sits on the TOP edge"
    assert [y for _x, y in home_cap] == [box_h, box_h, box_h - 4.6], (
        "home's cap sits on the BOTTOM edge")


def test_the_two_markers_carry_different_colours():
    """The `same colour` break. Every marker still draws under it — the picture is merely wrong
    about whose is whose — so the assertion has to be about the colours themselves.
    """
    svg = _two()
    assert AWAY_COLOR in svg and HOME_COLOR in svg
    # Three apiece: the cap, the rule, and the figure's own label — the label carries the team
    # colour too, which is what makes the number under the axis attributable at a glance.
    assert svg.count(AWAY_COLOR) == 3, "away's cap, rule and label"
    assert svg.count(HOME_COLOR) == 3, "home's cap, rule and label"
    caps = re.findall(r"<polygon points='[^']+' fill='([^']+)'", svg)
    assert caps[0] != caps[1], "the two caps must not be the same colour"


def test_two_teams_with_the_SAME_figure_do_not_collide():
    """🚨 MEASURED, NOT IMAGINED: 10.1% of the games that render this panel have at least one of
    its six rows tied (372 of 3,674 on `srv_game_team`); `first_downs` alone ties in 4.74%. One
    game in ten, which is why above/below is load-bearing rather than tidy.

    Both markers land on the same x — they must, they are the same number — and they are still
    two distinguishable marks because they occupy different halves.
    """
    svg = distribution.box(_box_row(), value=180, value_below=180, width=300,
                           value_color=AWAY_COLOR, value_below_color=HOME_COLOR)
    (ax, ay1, ay2), (hx, hy1, hy2) = _value_rules(svg)
    assert ax == hx, "the same figure is the same place on the axis"
    assert (ay1, ay2) != (hy1, hy2), "and yet they are not the same mark"
    assert len(_polys(svg)) == 2, "two caps, one per team"


def test_position_survives_two_teams_sharing_a_colour():
    """🚨 AC-G.22, AND THE CASE HUE CANNOT ANSWER: two teams whose brand colours are the same red.
    Nothing prevents it and nothing upstream will. With colour contributing nothing, the reader
    is left with position — and position still separates them completely.
    """
    same = "light-dark(#a6192e, #ff6b7d)"
    svg = distribution.box(_box_row(), value=180, value_below=240, width=300,
                           value_color=same, value_below_color=same)
    rules = _value_rules(svg)
    assert len({(y1, y2) for _x, y1, y2 in rules}) == 2, (
        "with one colour between them, the halves are the ONLY thing telling the reader "
        "which mark is which")


def test_a_side_with_no_figure_leaves_the_other_where_it_was():
    """⚠️ `value_below=None` MEANS *this side has no figure*, and it is NOT the same as not
    passing it. One team having the measure and the other not is a real state; when it happens,
    away's marker must stay in the UPPER half, because the half is what identifies the team.
    Sliding it to the one-value centre position would quietly relabel it as home's.
    """
    svg = distribution.box(_box_row(), value=180, value_below=None, width=300,
                           value_color=AWAY_COLOR)
    (_x, y1, y2), = _value_rules(svg)
    assert (y1, y2) == (0.0, distribution.BOX_HEIGHT / 2.0), "still the upper half"
    assert f"height='{distribution.LABEL_BAND + distribution.BOX_HEIGHT + 15}'" in svg, (
        "and the band above is still reserved, so a column of these rows stays aligned")

    only_home = distribution.box(_box_row(), value=None, value_below=240, width=300,
                                 value_below_color=HOME_COLOR)
    (_x2, hy1, hy2), = _value_rules(only_home)
    assert (hy1, hy2) == (distribution.BOX_HEIGHT / 2.0, float(distribution.BOX_HEIGHT))


def test_a_team_with_no_colour_still_draws():
    """⚠️ 10.89% of games have a side with no sourced colour (B109). A missing colour is a
    fallback, never a missing marker.
    """
    svg = distribution.box(_box_row(), value=180, value_below=240, width=300)
    assert len(_value_rules(svg)) == 2
    assert svg.count(distribution.VALUE_COLOR) >= 4, "both markers fall back to the accent"


def test_the_frame_stretches_around_BOTH_figures():
    """A frame built from one side would draw the other outside the viewBox — the same clipping
    defect the single-value frame already guards against, one side over."""
    svg = distribution.box(_box_row(), value=-50, value_below=600, width=300)
    xs = [x for x, _y1, _y2 in _value_rules(svg)]
    assert all(0 <= x <= 300 for x in xs), f"both markers inside the frame: {xs}"


def test_the_two_labels_sit_on_their_own_baselines():
    """✅ AND THIS IS WHY THE SECOND VALUE DOES NOT COST A LABEL. Labels collide only with labels
    on the SAME baseline, so away's figure competes with nothing at all. Measured across
    120/200/300/448: the two-value chart draws MORE labels than the one-value chart in ~75% of
    random pairs and fewer in under 3%.
    """
    svg = _two()
    ys = {y for y in re.findall(r"<text x='[-\d.]+' y='([-\d.]+)'", svg)}
    assert len(ys) == 2, f"two label baselines, one per side: {ys}"
    assert min(float(y) for y in ys) < 0, "away's label is ABOVE the box"


def test_a_missing_side_is_NAMED_rather_than_silently_half_drawn():
    """⚠️ AC-G.11: an absence must say WHICH absence it is, and the aria-label is all a screen
    reader gets. Two figures and one figure are different pictures — narrating both as
    "box and whisker" would report agreement between sides where one side has no number.

    🚨 AND THE ONE-VALUE CHART'S LABEL IS UNCHANGED, because B108's call site is live.
    """
    both = distribution.box(_box_row(), value=180, value_below=240, width=300, label="Yards")
    assert "aria-label='Yards: box and whisker, two values'" in both

    one = distribution.box(_box_row(), value=180, value_below=None, width=300, label="Yards")
    assert "one value — the other side has none" in one

    neither = distribution.box(_box_row(), value=None, value_below=None, width=300,
                               label="Yards")
    assert "neither side has a value" in neither

    legacy = distribution.box(_box_row(), value=180, width=300, label="Yards")
    assert "aria-label='Yards: box and whisker'" in legacy, "unchanged for the live call site"
