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

from lib import distribution, fmt                  # noqa: E402
# ⚠️ A154 imports `fmt` for `precision_for`: the decimal rule is keyed on the metric name
# and lives in ONE table, so the test reads that table rather than restating its answers.


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


# --- A133: the labels stop overprinting ---------------------------------------------------
#
# 🚨 THE DEFECT WAS ON THE LIVE SITE AND IT WAS REPRODUCED ON REAL ROWS BEFORE IT WAS FIXED.
# 64,213 charts the Matchup panel actually renders — every (game, metric) pair joined to its
# own week's distribution — measured against RENDERED GLYPH BOXES rather than a character
# model: at B111's shipped width of 110px, 11.22% of advanced charts and 6.08% of box-score
# charts had at least one overlapping label pair. After: 0.00% at every width, both panels.
#
# ⚠️ B111 RASTERED ITS OWN PANEL AND FOUND 0 OF 49 PAIRS, AND THAT WAS NOT WRONG — it is one
# game's eighteen box-score rows, where the rate is 6%. Expected hits: about one. Zero is an
# ordinary draw from that sample, not evidence of absence.

_PLAYS_ROW = {"n": 100, "team_games_in_week": 100,
              "p25": 59.0, "p50": 66.0, "p75": 74.0,
              "whisker_low": 41.0, "whisker_high": 94.0, "outlier_count": 0}


def _placed(svg):
    """Every drawn label as (x, baseline, text)."""
    return [(float(x), float(y), t) for x, y, t in re.findall(
        r"<text x='([-\d.]+)' y='([-\d.]+)'[^>]*>([^<]*)</text>", svg)]


def _overlapping_pairs(svg):
    """Pairs whose ink boxes intersect. text-anchor=middle, so each spans x ± width/2."""
    labels = _placed(svg)
    bad = []
    for i in range(len(labels)):
        xi, yi, ti = labels[i]
        for j in range(i + 1, len(labels)):
            xj, yj, tj = labels[j]
            if yi != yj:
                continue                      # different baselines cannot collide
            need = (distribution._text_width(ti) + distribution._text_width(tj)) / 2.0
            if abs(xi - xj) < need:
                bad.append((ti, tj, round(need - abs(xi - xj), 2)))
    return bad


def test_the_label_width_is_measured_per_character_not_averaged():
    """🚨 THE DIGITS ARE PROPORTIONAL AND `len(text)` CANNOT SEE IT.

    Measured in Chromium at font-size 9 in the font the page resolves: `1` is 4.344px and `4`
    is 5.969px, a 37% spread. So `111.1` and `444.4` are the same LENGTH and differ by 6.5px
    of ink — and the old model, `len(text) * 2.6` a half, charged both exactly 26.0px.

    ⚠️ The floor was the worse half: a single digit was charged 18.0px for 5.3px of ink, which
    is why short labels used to be pushed apart for no reason.
    """
    narrow, wide = distribution._text_width("111.1"), distribution._text_width("444.4")
    assert narrow < wide, "a per-character sum must distinguish 1 from 4"
    assert wide - narrow > 5.0, f"the spread is real: {narrow:.2f} vs {wide:.2f}"
    assert distribution._text_width("7") < 7.0, "a single digit is not 18px wide"
    # An unmeasured character is charged the widest thing in the table, never the narrowest:
    # erring wide drops a label, erring narrow overprints one.
    assert distribution._text_width("W") == distribution._ADVANCE_FALLBACK


def test_no_two_drawn_labels_overlap():
    """🚨 THE PROPERTY, ON THE REAL ROW THAT PRODUCED THE DEFECT.

    `offense_plays` in 2026: whiskers 41–94, quartiles 59/66/74, this game 67 and 76, drawn at
    B111's shipped 110px with `dp=2`. Before the fix this chart rendered `41.0059.00` and
    `76.0094.00` — four real numbers overprinted into two strings that are none of them.
    """
    svg = distribution.box(_PLAYS_ROW, width=110, dp=2, value=67.0, value_below=76.0)
    assert _overlapping_pairs(svg) == [], f"labels overlap: {_overlapping_pairs(svg)}"


def test_no_two_drawn_labels_overlap_when_one_is_much_LONGER():
    """🚨 THE CASE THAT DECIDES MULTIPLIER versus ADDITIVE, AND THEY DISAGREE MOST HERE.

    A multiplier scales its allowance with the label, so it is most permissive exactly where
    the labels are longest — `(half + other_half) * 0.86` forgives 3.6px between two 5-character
    labels and 4.0px between two 6-character ones. An additive gap forgives a constant, which
    is what clear space actually is.
    """
    svg = distribution.box(_PLAYS_ROW, width=110, dp=2, value=67.0, value_below=76.0,
                           value_label="-12.75", value_below_label="-108.25")
    assert _overlapping_pairs(svg) == [], f"long labels overlap: {_overlapping_pairs(svg)}"


def test_a_label_that_cannot_fit_is_actually_DROPPED():
    """⚠️ THE OTHER HALF, AND WITHOUT IT THE TWO ABOVE PASS ON A PLACER THAT NEVER DROPS
    ANYTHING. A threshold of zero satisfies "nothing overlaps" trivially by drawing every label
    wherever it lands — which is the §6 failure mode by name: an absence test that passes
    because the thing doing the looking was switched off.

    At 110px this chart has six labels' worth of numbers and room for a few of them.
    """
    svg = distribution.box(_PLAYS_ROW, width=110, dp=2, value=67.0, value_below=76.0)
    drawn = {t for _x, _y, t in _placed(svg)}
    possible = {"41.00", "59.00", "66.00", "74.00", "94.00", "67.00", "76.00"}
    assert drawn < possible, "nothing was dropped — the collision test is not running"
    assert drawn, "everything was dropped — the collision test is too strict to draw a chart"


def test_the_clearance_is_additive_rather_than_a_fraction_of_the_labels():
    """The shape of the rule, pinned. `(half + other_half)` IS the touching condition; anything
    beyond it is clear space, and clear space is a constant.

    ⚠️ A FACTOR BELOW 1.0 IS AN ALLOWANCE FOR OVERLAP. That is what `0.86` was, and naming it
    as a deliberate allowance is what made it obviously wrong once anybody looked.
    """
    assert distribution.LABEL_GAP > 0, "some clear space is wanted"
    assert distribution.LABEL_GAP < 6, "but a constant, not a wedge"


def test_the_PLACER_uses_the_measured_width_not_just_the_helper():
    """🚨 THIS TEST EXISTS BECAUSE A STAGED BREAK CAME BACK GREEN.

    A133 staged three breaks. The third put the old `max(len(text) * 2.6, 9.0)` model back
    inside `place()` while leaving `_text_width` correct and leaving the additive gap in place —
    and ALL THIRTY-NINE TESTS PASSED. The overprint did not return, because `len * 2.6` is
    WIDER than the real ink for most labels: it over-reserves, so it drops labels that would
    have fitted but never lets two collide.

    ⚠️ SO THE TWO HALVES OF THE FIX ARE NOT EQUALLY LOAD-BEARING, AND SAYING SO MATTERS. The
    THRESHOLD is what stopped the overprinting. The MEASURED WIDTHS are what stop labels being
    dropped for no reason — worth ~0.09 labels a chart back on the box-score panel at 110px.

    🚨 AND THE GAP WAS IN THE TEST, NOT THE CODE: asserting `_text_width` is correct says
    nothing about whether the placer CALLS it. A correct helper nobody uses is the dead-copy
    class. This asserts the placer's own behaviour instead.

    The edge clamp is where the two models are separable — `x` is clamped to
    `pad + half - 8` — but ONLY for a label wide enough that the clamp actually binds.

    ⚠️ AND GETTING THAT WRONG IS WHY THIS DOCSTRING SAYS IT. The first draft asserted on a
    two-character label, whose natural x of 10.0 already sits right of its own clamp bound of
    7.16, so the clamp never fired and the test failed against CORRECT code. `41.00` at `dp=2`
    binds: 14.42px under the measured half of 12.42, 15.00px under the old floor of 13.00.
    """
    row = dict(_PLAYS_ROW, p25=41.0, p50=41.0, p75=41.0, whisker_low=41.0, whisker_high=94.0)
    svg = distribution.box(row, width=300, dp=2, ticks=distribution.TICK_BOUNDS,
                           show_value=False)
    xs = {t: x for x, _y, t in _placed(svg)}
    assert "41.00" in xs, "the lower boundary label must be drawn"
    # 10 (pad) + _text_width("41.00")/2 - 8 = 14.42.  Under max(len*2.6, 9.0): 15.00.
    expected = 10.0 + distribution._text_width("41.00") / 2.0 - 8.0
    assert abs(xs["41.00"] - expected) < 0.1, (
        f"the leftmost label sits at {xs['41.00']}, expected {expected:.2f} — the placer is "
        "not clamping by the MEASURED width, so it is not using _text_width")


# --- A139: `frame=` puts two charts on one scale (cfdb-wta-R-927) -------------------------

def _serif_xs(svg: str):
    """The two whisker serifs' x positions — where the boundaries are DRAWN."""
    return sorted({float(x) for x in
                   re.findall(r"<line x1='([-\d.]+)' y1='[\d.]+' x2='\1'", svg)})


def test_the_frame_moves_the_scale_and_moves_no_label():
    """🚨 cfdb-wta-R-927, AND BOTH HALVES ARE THE TEST.

    📊 B114 measured the defect on Marc's gained-over-allowed pair: two `box()` calls stacked
    vertically frame on their OWN whiskers, so `total` drew 416.5 yards of range on the top row
    and 366.0 on the bottom across the same pixels — a 13.8% scale difference in a layout that
    invites a reader to compare the two by eye.

    ✅ SO `frame=` HAS TO MOVE THE PIXELS. A test that only checked the labels would pass on a
    parameter that did nothing at all.

    ❌ AND IT MUST MOVE NOTHING THAT PRINTS. `lo`/`hi` draw the whisker rule, its serifs and the
    boundary labels; relabelling them with the union's numbers would tell the reader this team's
    week ran from 142.5 when it ran from 204.0. That is the version B114 refused to fake from the
    page, and it is one line away from the honest one.
    """
    row = _box_row(whisker_low=204.0, whisker_high=620.5,
                   p25=300.0, p50=400.0, p75=500.0)

    narrow = distribution.box(row, value=450.0, width=240, show_value=True, dp=1)
    wide = distribution.box(row, value=450.0, width=240, show_value=True, dp=1,
                            frame=(142.5, 620.5))

    assert _drew(narrow) and _drew(wide)

    # ✅ THE PIXELS MOVED. A wider frame pushes this row's own whisker boundaries inward.
    assert _serif_xs(narrow) != _serif_xs(wide), (
        "frame= did nothing — the scale is unchanged, so two stacked rows still disagree")
    assert _serif_xs(wide)[0] > _serif_xs(narrow)[0], (
        "widening the frame at the LOW end must move this row's low serif to the RIGHT")

    # ❌ AND NOTHING THAT PRINTS MOVED WITH IT.
    assert [text for _x, text in _texts(narrow)] == [text for _x, text in _texts(wide)], (
        "a frame must not change a single printed figure — the labels are this row's own")
    assert "142.5" not in wide, (
        "the union's bound reached a label: that is the dishonest shared axis, not this one")
    assert "204.0" in wide, "this row's real low boundary must still print"


def test_a_narrower_frame_is_inert_rather_than_clipping():
    """⚠️ IT WIDENS AND NEVER REPLACES, which is the property the existing outlier comment
    protects: *"an outlier pinned to the boundary reads as 'at the extreme' when the truth is
    'beyond it'"*. A caller handing in a frame narrower than the data must therefore change
    nothing, rather than clamping real marks to its bounds.
    """
    row = _box_row(whisker_low=204.0, whisker_high=620.5)
    plain = distribution.box(row, value=450.0, width=240)
    narrowed = distribution.box(row, value=450.0, width=240, frame=(300.0, 400.0))
    assert narrowed == plain, "a frame inside the data must be inert, not clipping"


def test_the_frame_still_lets_a_value_outside_the_union_widen_it():
    """🚨 THE OUTLIER RULE SURVIVES THE SHARED AXIS. A team beyond the week's union is drawn
    beyond it — the frame is a floor on the scale, not a ceiling on the data.
    """
    row = _box_row(whisker_low=204.0, whisker_high=620.5)
    beyond = distribution.box(row, value=900.0, width=240, frame=(142.5, 620.5))
    assert _drew(beyond)
    marker_xs = [float(x) for x in re.findall(r"<line x1='([-\d.]+)'[^>]*stroke-width='2", beyond)]
    assert marker_xs, "the value marker must still be drawn"
    # It is the rightmost mark on the chart, because 900 is past both the whisker and the union.
    assert max(marker_xs) >= max(_serif_xs(beyond)), (
        "a value beyond the union was pulled back to the frame — the clamping defect")


def test_two_stacked_rows_share_one_scale_when_framed_on_their_union():
    """✅ THE THING THE PARAMETER IS FOR, END TO END, at B114's own measured numbers.

    Framed on the union, one yard is the same number of pixels on both rows — which is what makes
    the vertical stack readable. Unframed it is not, and that difference is asserted rather than
    assumed.
    """
    gained = _box_row(whisker_low=204.0, whisker_high=620.5,
                      p25=300.0, p50=400.0, p75=500.0)
    allowed = _box_row(whisker_low=142.5, whisker_high=508.5,
                       p25=250.0, p50=330.0, p75=430.0)
    union = (142.5, 620.5)

    def span_per_unit(svg, lo, hi):
        serifs = _serif_xs(svg)
        return (serifs[-1] - serifs[0]) / (hi - lo)

    unframed = (span_per_unit(distribution.box(gained, show_value=False, width=240),
                              204.0, 620.5),
                span_per_unit(distribution.box(allowed, show_value=False, width=240),
                              142.5, 508.5))
    # ⚠️ THE TOLERANCE IS THE SVG's OWN PRINT PRECISION, NOT A MAGIC NUMBER. Coordinates are
    # emitted at one decimal place, so each serif carries up to ±0.05px of rounding and the
    # derived pixels-per-yard can differ by 0.1 / (hi − lo) between two rows that agree exactly.
    # On this pair that bound is 0.1 / 416.5 = 0.00024.
    quantisation = 0.1 / (620.5 - 204.0)
    assert abs(unframed[0] - unframed[1]) > 10 * quantisation, (
        "the two rows already agreed, so this fixture cannot show the defect")

    framed = (span_per_unit(distribution.box(gained, show_value=False, width=240, frame=union),
                            204.0, 620.5),
              span_per_unit(distribution.box(allowed, show_value=False, width=240, frame=union),
                            142.5, 508.5))
    assert abs(framed[0] - framed[1]) <= quantisation, (
        f"framed on the union, one yard must be the same width on both rows: "
        f"{framed[0]:.6f} against {framed[1]:.6f}")


# --- A142: the whiskers were already Tukey's; the OUTLIERS were the missing half ----------
#
# 🚨 MARC ASKED FOR SOMETHING THAT WAS ALREADY THERE AND FOR SOMETHING THAT WAS NOT, IN ONE
# SENTENCE: *"can we add the data points to also show the IQR whiskers and make it available to
# the box-whisker plots on the site?"* The whiskers `box()` draws ARE the 1.5*IQR fences — Tukey's,
# reaching the most extreme observation inside the fence — and a round that rebuilt them would
# have shipped nothing. `min_value`, `max_value` and `outlier_count` are all published and none of
# the three was drawn, which is the half worth building.

def _outlier_row(**over):
    """A row whose extremes lie OUTSIDE its whiskers — the state the rings exist for.

    🚨 R-744, ASKED OF THIS FIXTURE: what do its defaults make true? The whiskers here are 128/690
    and the extremes 90/856, so BOTH sides are outside and neither ring can be drawn by accident.
    ⚠️ AND THE TWO DISTANCES ARE DELIBERATELY UNEQUAL (38 low, 166 high): a fixture symmetric about
    its own whiskers would let a break that swapped `min_value` and `max_value` pass unnoticed.
    """
    row = {"n": 135, "team_games_in_week": 135,
           "p25": 312.5, "p50": 393.0, "p75": 480.0,
           "whisker_low": 128.0, "whisker_high": 690.0,
           "min_value": 90.0, "max_value": 856.0, "outlier_count": 2}
    row.update(over)
    return row


def _circles(svg: str):
    """Every ring the box drew, as (cx, r)."""
    return [(float(cx), float(r)) for cx, r in
            re.findall(r"<circle cx='([-\d.]+)' cy='[-\d.]+' r='([\d.]+)'", svg)]


def test_the_whiskers_drawn_are_the_iqr_FENCES_and_not_the_range():
    """📊 THE PICTURE THAT ANSWERS THE FIRST HALF OF MARC'S QUESTION.

    The serifs sit at `whisker_low`/`whisker_high` and the printed boundary labels are those two
    figures. `min_value` and `max_value` are on the row, differ from them, and appear nowhere.

    ⚠️ KEYED ON THE LABELS AND THE GEOMETRY TOGETHER, because either alone is weak: a label could
    be right with the serif in the wrong place, and R-820 is the round where the geometry was right
    for two of three vocabularies while a reader got an em dash.
    """
    row = _outlier_row()
    svg = distribution.box(row, width=300)
    printed = {text for _x, text in _texts(svg)}
    assert "128.0" in printed and "690.0" in printed, \
        f"the whisker FENCES are the boundary labels; got {printed}"
    assert "90.0" not in printed and "856.0" not in printed, \
        "min_value/max_value are not the whiskers and must not be printed as them"


def test_the_extremes_are_not_drawn_unless_a_caller_asks():
    """⚠️ §3 rule 3.1: THE DEFAULT IS WHAT EVERY EXISTING CALLER GETS. `matchup.py` is session B's
    and did not move this round, so the bytes it renders must not move either.

    🚨 AND THIS IS A STRING EQUALITY RATHER THAN AN ABSENCE CHECK, because `assert "<circle" not in
    svg` would also pass if the whole chart had stopped drawing — §6 mode 1, which this file has
    already been bitten by once (R-820).
    """
    row = _outlier_row()
    assert _drew(distribution.box(row, value=497.0, width=300)), "the chart must still draw"
    assert distribution.box(row, value=497.0, width=300) == \
        distribution.box(row, value=497.0, width=300, outliers=False)
    assert _circles(distribution.box(row, value=497.0, width=300)) == []


def test_a_ring_marks_each_extreme_that_lies_beyond_its_whisker():
    """Both sides of `_outlier_row` are outside, so both rings draw — and they are OUTSIDE the
    serifs, which is the only place in this chart nothing else can be."""
    svg = distribution.box(_outlier_row(), width=300, outliers=True)
    rings = _circles(svg)
    assert len(rings) == 2, f"one per extreme beyond a whisker; got {rings}"
    serifs = sorted(float(x) for x in re.findall(r"<line x1='([-\d.]+)' y1='[\d.]+' "
                                                 r"x2='[-\d.]+' y2='[\d.]+' "
                                                 r"stroke='currentColor' stroke-width='1' "
                                                 rf"opacity='{distribution.WHISKER_OPACITY:g}'", svg))
    low_ring, high_ring = sorted(cx for cx, _r in rings)
    assert low_ring < min(serifs), "the low ring sits beyond the low whisker serif"
    assert high_ring > max(serifs), "the high ring sits beyond the high whisker serif"


def test_no_ring_is_drawn_where_the_extreme_IS_the_whisker():
    """🚨 THE DRAW RULE IS GEOMETRIC, AND `outlier_count` CANNOT DECIDE IT.

    📊 REAL DATA, 2026 regular week 2 `total_yards` at game grain: `outlier_count` 2, `whisker_low`
    128 and `min_value` 128 — BOTH outliers are on the high side. A ring keyed on the count alone
    would draw one at 128 sitting exactly on the serif, claiming to be beyond a boundary it is on.
    """
    one_sided = _outlier_row(min_value=128.0)
    rings = _circles(distribution.box(one_sided, width=300, outliers=True))
    assert len(rings) == 1, f"only the high side is outside; got {rings}"

    none_outside = _outlier_row(min_value=128.0, max_value=690.0, outlier_count=0)
    assert distribution.box(none_outside, width=300, outliers=True) == \
        distribution.box(none_outside, width=300), \
        "a week with nothing outside its whiskers draws the same picture either way"


def test_the_ring_widens_the_frame_rather_than_being_clamped_to_the_edge():
    """🚨 THE MODULE'S OWN RULE, APPLIED TO THE NEW MARK: *"an outlier pinned to the boundary reads
    as 'at the extreme' when the truth is 'beyond it'"*.

    ⚠️ R-843 — A PIN IS ONLY A PIN IF THE BREAK MOVES IT. The clamping break is the plausible one
    here (it keeps the chart tidy), and it would leave the ring's cx sitting on the pad and the box
    exactly where it was. So BOTH halves are asserted: the ring is inside the viewBox AND the box
    got narrower, which clamping cannot produce.
    """
    row = _outlier_row()
    plain = distribution.box(row, width=300)
    widened = distribution.box(row, width=300, outliers=True)

    def box_width(svg):
        return float(re.search(r"<rect x='[-\d.]+' y='[-\d.]+' width='([\d.]+)'", svg).group(1))

    assert box_width(widened) < box_width(plain), (
        "the frame took in 90.0 and 856.0, so p25-p75 must occupy fewer pixels — "
        f"{box_width(widened)} against {box_width(plain)}")
    for cx, r in _circles(widened):
        assert 0 <= cx - r and cx + r <= 300, f"ring at {cx} is clipped by the viewBox"


def test_the_outliers_reach_a_reader_who_cannot_see_the_rings():
    """🚨 AC-G.11, AND IT IS A139's FINDING RUN IN REVERSE. There the sighted reader was the one
    told less than the screen-reader user; a ring nobody narrates is the same defect facing the
    other way."""
    svg = distribution.box(_outlier_row(), width=300, outliers=True, label="Total yards")
    reading = re.search(r"aria-label='([^']*)'", svg).group(1)
    assert "2 beyond the whiskers" in reading, reading
    quiet = distribution.box(_outlier_row(), width=300, label="Total yards")
    assert "beyond the whiskers" not in re.search(r"aria-label='([^']*)'", quiet).group(1), \
        "a chart that drew no rings must not claim any"


def test_the_tooltip_says_how_many_are_outside_and_how_far_they_reach():
    """⚠️ THE TOOLTIP IS THE ONE PLACE THE FIGURES CAN GO WITHOUT COSTING PIXELS, and `describe()`
    is shared, so this fact arrives on the thumbnail and the panel too — both of which had exactly
    the same silence about the tail."""
    text = distribution.describe(_outlier_row())
    assert "2 beyond the whiskers (90.0 to 856.0)" in text, text
    assert "beyond the whiskers" not in distribution.describe(_outlier_row(outlier_count=0))


def test_a_mark_can_carry_its_own_hover_and_the_words_are_the_callers():
    """📊 MEASURED IN A REAL BROWSER BEFORE BEING BUILT: `<title>` survives Streamlit's sanitiser
    as a child of `<svg>`, `<circle>`, `<line>` and `<g>` — which is not a given, because this
    codebase has already lost `onclick` to that sanitiser (`table.py` records it).

    ⚠️ THE TEXT IS ESCAPED because it is element CONTENT and it comes from a caller — B118's
    tooltip is *"Week #, Opponent Rank, Name, Record, Final Score"*, which is team names and
    therefore arbitrary text.
    """
    svg = distribution.box(_outlier_row(), value=497.0, width=300,
                           value_title="Oregon <b> & Ohio State")
    assert "<title>Oregon &lt;b&gt; &amp; Ohio State</title>" in svg, svg[:400]
    assert distribution.box(_outlier_row(), value=497.0, width=300).count("<title>") == 0, \
        "no caller asked for a mark tooltip, so no mark carries one"


def test_the_hover_the_chart_ALREADY_had_is_still_there():
    """🚨 R-805's SHAPE, CAUGHT WHILE ANSWERING MARC: the claim *"there is no hover on any mark"*
    was made from a grep that found two `title=` occurrences. There are six, and three of them are
    `describe(row)` — on `thumbnail`, on `panel`, and on `box()` itself. A round that had believed
    the grep would have built a tooltip beside one that already worked.
    """
    html = distribution.box(_outlier_row(), value=497.0, width=300)
    assert html.startswith("<span class='cfdb-dist' title='"), html[:80]
    assert "n=135 of 135 team-games" in html


def test_a_row_that_does_not_carry_the_new_columns_degrades_rather_than_inventing():
    """🚨 MEASURED ON THE LIVE PAGE, AND IT IS THE LIMIT OF WHAT THIS ROUND COULD SHIP.

    📊 `matchup.py` selects its distribution columns by name, and NEITHER LIST CARRIES
    `outlier_count`:

        _DISTRIBUTION_COLUMNS      (before-game)  no outlier_count, no min_value, no max_value
        _DISTRIBUTION_ROW_COLUMNS  (post-game)    min_value and max_value, no outlier_count

    ✅ So `describe()`'s new sentence is INERT on the live page today and this round says so rather
    than claiming the tooltip improved — §3 rule 3.1: a shared-module change ships the parameter
    and the default, and the call sites in session B's file are B's to consume on B's own round.

    ⚠️ WHAT THIS TEST PINS IS THE PROPERTY THAT OUTLIVES THAT: a row missing any of the three
    columns must draw and describe exactly as it did before, never raise, and never print a figure
    it was not given. A KeyError here would take out both tabs of a page this round must not touch.
    """
    full = _outlier_row()
    before_game = {k: v for k, v in full.items()
                   if k not in ("outlier_count", "min_value", "max_value")}
    post_game = {k: v for k, v in full.items() if k != "outlier_count"}

    assert "beyond the whiskers" not in distribution.describe(before_game)
    assert _circles(distribution.box(before_game, width=300, outliers=True)) == [], \
        "no extremes on the row means nothing to draw, not a guess"
    assert distribution.box(before_game, width=300, outliers=True) == \
        distribution.box(before_game, width=300)

    # The post-game list HAS the extremes, so the geometry works and only the COUNT is silent.
    assert len(_circles(distribution.box(post_game, width=300, outliers=True))) == 2
    reading = re.search(r"aria-label='([^']*)'",
                        distribution.box(post_game, width=300, outliers=True)).group(1)
    assert "extremes beyond the whiskers" in reading, (
        "with no count to quote it must still say the rings are there — an unnarrated mark is "
        f"the AC-G.11 defect this file already fixed once; got {reading}")


# --- A145: the box gets a height (cfdb-main-R-992) -----------------------------------------
#
# > **MARC, v16:** *"The circles need to be overlayed on top of the Box-Whisker with same x and
# > y-axis. The box-whisker will have to be taller to accommodate the circles that will cover
# > full regular season schedule (even with 50% overlap)."*

def _tall_row(**over):
    row = {"n": 370, "weeks_counted": 2, "p25": 255.5, "p50": 367.0, "p75": 474.8,
           "whisker_low": 57.0, "whisker_high": 762.0,
           "min_value": 57.0, "max_value": 856.0, "outlier_count": 1}
    row.update(over)
    return row


def _svg_height(svg: str) -> float:
    return float(re.search(r"<svg viewBox='0 0 [\d.]+ ([\d.]+)'", svg).group(1))


def _rect(svg: str):
    """(y, height) of the p25–p75 rect."""
    match = re.search(r"<rect x='[-\d.]+' y='([-\d.]+)' width='[\d.]+' height='([\d.]+)'", svg)
    return float(match.group(1)), float(match.group(2))


def test_the_default_height_renders_the_same_bytes_as_before_the_parameter():
    """🚨 §3 rule 3.1, AND THE HASH IS THE ASSERTION RATHER THAN A SPOT CHECK.

    ⚠️ THIS TEST EXISTS BECAUSE THE FIRST DRAFT FAILED IT. Making `height` a float so the ratios
    could be computed turned the viewBox's `41` into `41.0` — **580 of 600 renders changed** while
    every picture stayed pixel-identical and every other test passed. A spot check on one call
    would have missed it; comparing against the pre-change module did not.

    ✅ THE CORPUS IS WIDE ON PURPOSE: widths, values, tick strategies, one- and two-sided modes,
    outliers on and off, and a caller-supplied frame. It is cheap and it is the only thing standing
    between a default parameter and a site-wide re-render.

    ⚠️ **THE ONE-OFF PROOF IS NOT HERE AND CANNOT BE**, which is worth saying rather than faking.
    Byte-identity was established by importing `site/lib/distribution.py` at `8294b2d` ALONGSIDE
    this one and diffing 600 renders — **0 differences, matching sha256** — and that comparison
    needs the old module, which a test in this repo does not have. 🚨 A FROZEN DIGEST LITERAL WOULD
    BE WORSE THAN NOTHING: it pins whatever the code produced the day it was written, so it goes
    red on any deliberate change to the default picture and says "bytes moved" rather than "this
    change was unintended". The report carries the measurement; this carries the PROPERTY.

    ✅ THE PROPERTY IS THE HALF THAT CAN LIVE IN CI: passing the default explicitly must be
    indistinguishable from not passing it, across the whole parameter space. That is what a
    default MEANS, and it is what breaks first if the ratios stop returning their literals at 26px.

    ⚠️ A155 MOVED THE SERIF LITERAL FROM 5.0 TO 7.5 — Marc's v19, *"increase the size of the
    whisker outer boundary lines by 50%"* — and this test is the ONLY thing in the suite that went
    red on it. 🚨 THAT IS WORTH KNOWING RATHER THAN QUIETLY FIXING: bytes moved on every chart on
    the site and one assertion noticed, because nothing else pins the serif's y at all. The
    inverted proof lives in `test_the_serif_is_the_only_thing_that_moved` below.
    """
    for width in (120, 240, 300, 448):
        for value in (None, 180.0, 900.0):
            for ticks in (distribution.TICK_PERCENTILES, distribution.TICK_BOUNDS,
                          distribution.TICK_NONE):
                for outliers in (False, True):
                    for below in ({}, {"value_below": 90.0}, {"value_below": None}):
                        kw = dict(value=value, width=width, ticks=ticks,
                                  outliers=outliers, label="T", **below)
                        assert distribution.box(_tall_row(), **kw) == \
                            distribution.box(_tall_row(), height=distribution.BOX_HEIGHT, **kw), (
                            f"width={width} value={value} ticks={ticks} outliers={outliers} "
                            f"below={below}: the explicit default is not the implicit one")
    # And the two ratios still land on the literals they replaced.
    assert distribution.BOX_HEIGHT * distribution._RECT_HALF_RATIO == 7.0
    # ⚠️ `approx`, AND ONLY ON THIS ONE. `5.0 / 26 * 26` came back exactly 5.0; A155's
    # `7.5 / 26 * 26` is 7.500000000000001, which is a property of the binary representation and
    # not of the change. It reaches the SVG through `:.1f`, so nothing printed can see it — but an
    # exact comparison here would read as a defect in the ratio rather than in the assertion.
    assert distribution.BOX_HEIGHT * distribution._SERIF_HALF_RATIO == pytest.approx(7.5)


def test_a_taller_box_is_taller_by_exactly_what_was_asked_for():
    """The band grows by the parameter and the label band below it does not move relative to it."""
    default = distribution.box(_tall_row(), width=420)
    tall = distribution.box(_tall_row(), width=420, height=56)
    assert _svg_height(default) == distribution.BOX_HEIGHT + 15
    assert _svg_height(tall) == 56 + 15, "the 15px label band rides on top of the plot band"
    assert _svg_height(tall) - _svg_height(default) == 56 - distribution.BOX_HEIGHT


def test_the_furniture_scales_and_the_x_of_every_value_does_not():
    """🚨 THE DESIGN DECISION, AS AN ASSERTION. A box plot's y carries nothing and its x carries
    everything, so a height change must move no number sideways.

    ⚠️ KEYED ON THE DRAWN COORDINATES RATHER THAN ON THE INPUTS — a test that checked the row was
    unchanged would assert that dictionaries are immutable.
    """
    def xs(svg):
        return (re.findall(r"x1='([\d.]+)'", svg)
                + re.findall(r"<rect x='([\d.]+)'", svg)
                + re.findall(r"<circle cx='([\d.]+)'", svg))

    assert xs(distribution.box(_tall_row(), value=497.0, width=420, outliers=True)) == \
        xs(distribution.box(_tall_row(), value=497.0, width=420, height=121, outliers=True)), \
        "a taller box moved a value sideways"

    short_y, short_h = _rect(distribution.box(_tall_row(), width=420))
    tall_y, tall_h = _rect(distribution.box(_tall_row(), width=420, height=52))
    assert (short_h, tall_h) == (14, 28), \
        f"the rect keeps its 7/26 proportion: 14 at 26px, 28 at 52px — got {short_h}, {tall_h}"
    assert short_y == 6.0 and tall_y == 12.0, "and stays centred in the band"


def test_the_median_spans_the_box_at_every_height():
    """⚠️ IT USED TO BE `mid ± 7`, A LITERAL. Left alone, a 1.8px rule stopping 7px either side of
    centre in a 56px band reads as a tick rather than as the box's divider — and Marc called the
    median bold on purpose."""
    for height, expected in ((26, 14.0), (52, 28.0)):
        svg = distribution.box(_tall_row(), width=420, height=height)
        median = re.search(r"y1='([\d.]+)' x2='[\d.]+' y2='([\d.]+)' stroke='currentColor' "
                           r"stroke-width='1.8'", svg)
        assert median, svg[:200]
        assert round(float(median.group(2)) - float(median.group(1)), 1) == expected
        _y, rect_h = _rect(svg)
        assert round(float(median.group(2)) - float(median.group(1))) == round(rect_h)


def test_the_height_range_b122_can_ask_for_all_render():
    """📊 B118 measured the two ends: fifteen circles at d=7 need **56px** at Marc's 50% overlap
    ceiling and **121px** at pitch 8. Both, and the default, must draw a real chart.

    ⚠️ `_drew` RATHER THAN A LENGTH CHECK — the em-dash placeholder is also a string, which is the
    assertion R-820 was missing.
    """
    for height in (26, 40, 56, 80, 121, 200):
        svg = distribution.box(_tall_row(), value=497.0, width=420, height=height,
                               outliers=True, label="Total yards")
        assert _drew(svg), f"height={height} drew no picture"
        assert _svg_height(svg) == height + 15
        assert "<circle" in svg, f"height={height} lost the outlier ring"


# --- A145 part 2: the denominator noun the cumulative view never had ----------------------

def test_a_cumulative_row_says_what_its_n_is_over():
    """🚨 THE PROMPT ASKED FOR `("weeks_counted", "weeks")` IN THE DENOMINATOR LIST AND THAT WOULD
    HAVE PRINTED A FALSE RATIO.

    `describe()`'s denominator format is `n={n} of {total} {noun}`, so that entry renders
    **`n=370 of 2 weeks`** — 370 counts team-games and 2 counts weeks, and "370 of 2" is not a
    fraction that can exist. ⚠️ **A span is not a denominator**, and the format string is what
    decides which a column becomes.

    ✅ `n=370 over 2 weeks` is the honest form: it says what a reader of a cumulative box needs,
    which is how much football is behind the number.
    """
    text = distribution.describe(_tall_row())
    assert "n=370 over 2 weeks" in text, text
    assert " of 2 weeks" not in text, "a span rendered as a denominator is a false ratio"
    assert "n=198 over 1 week" in distribution.describe(_tall_row(n=198, weeks_counted=1)), \
        "one week is singular"


def test_a_row_with_a_real_denominator_is_untouched_by_the_span():
    """The three sibling views keep their own noun — `weeks_counted` never overrides one."""
    sibling = _tall_row(team_games_in_week=370)
    del sibling["weeks_counted"]
    assert "n=370 of 370 team-games" in distribution.describe(sibling)
    both = _tall_row(team_games_in_week=370)
    assert "n=370 of 370 team-games" in distribution.describe(both), \
        "a row carrying both must prefer the real denominator"
    assert "over 2 weeks" not in distribution.describe(both)


def test_a_row_with_neither_still_degrades_rather_than_inventing():
    """⚠️ A143 PINNED THIS PROPERTY AND A145 MUST NOT SPEND IT. A row with no denominator and no
    span reports its `n` and claims no noun at all."""
    bare = _tall_row()
    del bare["weeks_counted"]
    text = distribution.describe(bare)
    # ⚠️ `"n=370 ·"` BECAME `"n=370\n"` IN A150 — the separator changed by instruction (Marc, v17:
    # one statement per line), not the property. **What this test pins is that the bare row claims
    # NO NOUN**, and that is unchanged: the assertion still reads the first statement in full and
    # still refuses both "over" and " of ".
    assert text.split("\n")[0] == "n=370", text
    assert "over" not in text and " of " not in text, text


# ── A150: MIN to MAX, and a tooltip that breaks ────────────────────────────────────────────

def _label_texts(svg: str) -> list:
    """The label STRINGS only.

    ⚠️ NOT NAMED `_texts`. This file already has one at line ~370 returning `(x, text)` PAIRS, and
    a second definition later in the module silently replaces it for every test above — which is
    exactly what happened while this block was being written: four unrelated tests failed with
    `ValueError: too many values to unpack`. **A test helper appended to a long file is a name
    collision waiting to happen, and the collision breaks the tests that were already passing.**
    """
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def _frame_span(svg: str) -> float:
    """The viewBox width — the frame, in the only place the SVG states it."""
    return float(re.search(r"<svg viewBox='0 0 ([\d.]+) ", svg).group(1))


def test_the_extremes_strategy_labels_marcs_four_and_neither_whisker_end():
    """> **MARC, v17:** *"label MIN, Max, 25pctl, 75pctl where there is room"*, and when asked what
    > the whisker ends should do: *"MIN and MAX should be labeled on the axis, the whisker
    > endpoints don't need to be labeled."*

    🚨 HE IS SWAPPING TWO LABELS, NOT ADDING TWO — so this asserts the ABSENCES as hard as the
    presences. A test that only checked min and max were there would pass on a chart printing
    six numbers, which is the opposite of what he asked for.
    """
    row = _tall_row()
    svg = distribution.box(row, width=420, ticks=distribution.TICK_EXTREMES, show_value=False)
    texts = _label_texts(svg)
    assert "57.0" in texts, texts          # min_value
    assert "856.0" in texts, texts         # max_value
    assert "255.5" in texts and "474.8" in texts, texts   # p25, p75
    # 🚨 whisker_high is 762.0 and is NOT labelled. min_value and whisker_low are both 57.0 on
    # this row, which is why the whisker assertion is made on the HIGH end — the only end where
    # the two values differ, and therefore the only end where the test can tell them apart.
    assert "762.0" not in texts, f"the whisker end must not be labelled: {texts}"
    assert "367.0" not in texts, f"the median is not in Marc's list: {texts}"


def test_the_extremes_strategy_widens_the_frame_because_a_label_must_be_inside_it():
    """A142's law applied to a label: a mark drawn at the extreme has to be inside the viewBox,
    or it sits at the boundary and tells the reader the minimum is somewhere it is not."""
    row = _tall_row()
    default = distribution.box(row, width=420, show_value=False)
    extremes = distribution.box(row, width=420, ticks=distribution.TICK_EXTREMES,
                                show_value=False)
    # The frame is the same pixel width; what changes is the VALUE RANGE mapped onto it, which
    # shows up as the position of a landmark both charts draw — the median rule.

    def median_x(svg):
        return float(re.search(r"<line x1='([\d.]+)'[^>]*stroke-width='1.8'", svg).group(1))
    assert median_x(default) != median_x(extremes), (
        "the scale did not move, so the frame did not widen")


def test_frame_extremes_widens_without_drawing_a_single_ring():
    """🚨 A142 WROTE THE WIDENING AS `if outliers`, WHICH MADE *widening implies rings* TRUE TOO.
    Marc asked for the frame and said nothing about rings, so the two are separable."""
    row = _tall_row()
    widened = distribution.box(row, width=420, frame_extremes=True, show_value=False)
    ringed = distribution.box(row, width=420, outliers=True, show_value=False)
    assert "<circle" not in widened, "frame_extremes must draw no rings"
    assert "<circle" in ringed, "outliers must still draw them"
    # Same scale both ways — the widening is identical, only the marks differ.

    def median_x(svg):
        return float(re.search(r"<line x1='([\d.]+)'[^>]*stroke-width='1.8'", svg).group(1))
    assert median_x(widened) == median_x(ringed)


def test_the_default_still_frames_on_the_whiskers_and_draws_nothing_new():
    """⚠️ A145's RULE: the explicit default must be indistinguishable from before. A caller that
    asks for none of the three ways in gets the chart it already had."""
    row = _tall_row()
    svg = distribution.box(row, width=420, show_value=False)
    assert "<circle" not in svg
    # whisker_high 762.0 is the frame's top, not max_value 856.0 — so the whisker serif sits at
    # the right-hand edge. If the frame had widened, it would not.
    serifs = re.findall(r"<line x1='([\d.]+)' y1='[\d.]+' x2='[\d.]+' y2='[\d.]+' "
                        r"stroke='currentColor' stroke-width='1'", svg)
    assert serifs, svg
    assert max(float(x) for x in serifs) > _frame_span(svg) - 12, (
        "the high whisker must still reach the frame edge at the default")


def test_the_tooltip_breaks_one_statement_per_line():
    """> **MARC, v17:** *"I like the new hover tooltip, but can you include a `<br>` between each
    > statement"* — with his own five-line sketch.

    ⚠️ AND `<br>` WOULD BE A DEFECT: every consumer is a NATIVE tooltip, which renders plain text.
    """
    text = distribution.describe(_tall_row())
    lines = text.split("\n")
    assert len(lines) == 5, lines
    assert lines[0].startswith("n=370")
    assert lines[1].startswith("p25") and lines[2].startswith("median") and lines[3].startswith("p75")
    assert "beyond the whiskers" in lines[4], lines
    assert "<br>" not in text, "a literal <br> would reach the reader as four characters"
    assert " · " not in text


def test_the_attribute_escaper_turns_the_break_into_a_numeric_reference():
    """A raw newline in an attribute is fragile between here and a browser; `&#10;` is not."""
    attr = distribution._attr(distribution.describe(_tall_row()))
    assert "&#10;" in attr and "\n" not in attr
    assert attr.count("&#10;") == 4, attr
    # And the three chart entry points actually route through it.
    for html in (distribution.box(_tall_row(), width=240),
                 distribution.thumbnail(_row()),
                 distribution.panel(_row())):
        assert "&#10;" in html, html[:120]


# ── A154: the furniture — Marc's v18 ────────────────────────────────────────────────────────

def test_the_structure_is_25_percent_darker_and_each_element_from_its_own_baseline():
    """> **MARC, v18:** *"Increase the darknes of Whisker structure/outline by 25%"*

    🚨 THE STRUCTURE HAS TWO WEIGHTS AND THE PROMPT SAID ONE. The whisker drew at `opacity='.55'`
    and the box outline at `stroke-opacity='.5'` — a different value AND a different attribute.
    Each darkens from its own baseline, which is what his sentence means when the thing being
    darkened is not uniform.
    """
    assert distribution.WHISKER_OPACITY == pytest.approx(0.55 * 1.25)
    assert distribution.BOX_OUTLINE_OPACITY == pytest.approx(0.5 * 1.25)
    svg = distribution.box(_tall_row(), width=420, show_value=False)
    assert f"opacity='{distribution.WHISKER_OPACITY:g}'" in svg
    assert f"stroke-opacity='{distribution.BOX_OUTLINE_OPACITY:g}'" in svg
    assert "opacity='.55'" not in svg and "stroke-opacity='.5'" not in svg


def test_the_extreme_lines_are_full_height_and_drawn_UNDERNEATH_the_box():
    """🚨 THE Z-ORDER AND THE HEIGHT ARE LOAD-BEARING, NOT STYLING.

    > **MARC, v18:** *"MIN/MAX should extend full height of the plot (to the exten of the Box).
    > Plot MIN/MAX below (underneath in the Z) so that if IQR and MIN/MAX are equal, should be
    > able to discern both on the chart."*

    A mark drawn at serif height, or appended after the box, fails that sentence exactly — so
    both properties are asserted rather than the line's mere presence.
    """
    svg = distribution.box(_tall_row(), width=420, show_value=False, extreme_lines=True)
    lines = re.findall(r"<line x1='([\d.]+)' y1='([\d.-]+)' x2='[\d.]+' y2='([\d.-]+)'[^>]*"
                       r"opacity='([\d.]+)'", svg)
    full = [ln for ln in lines if float(ln[1]) == 0.0]
    assert full, f"no full-height line was drawn: {svg[:200]}"
    # full height means the whole plot band, not the rect
    assert float(full[0][2]) == pytest.approx(distribution.BOX_HEIGHT)
    assert float(full[0][3]) == pytest.approx(distribution.EXTREME_LINE_OPACITY)
    # 🚨 UNDERNEATH: the line's markup must come BEFORE the rect, or SVG paints it on top.
    assert svg.index("y1='0'") < svg.index("<rect"), "the extreme line is not underneath the box"


def test_both_of_marcs_candidate_weights_are_available_and_neither_is_chosen_for_him():
    """R-895's pattern: he gave two numbers, so the module offers both and the round renders
    the pair rather than picking."""
    assert distribution.EXTREME_LINE_OPACITY == pytest.approx(0.55 * 0.75)
    assert distribution.EXTREME_LINE_OPACITY_LIGHTER == pytest.approx(0.55 * 0.5)
    light = distribution.box(_tall_row(), width=420, show_value=False, extreme_lines=True,
                             extreme_line_opacity=distribution.EXTREME_LINE_OPACITY_LIGHTER)
    assert f"opacity='{distribution.EXTREME_LINE_OPACITY_LIGHTER:g}'" in light


def test_yards_lose_their_decimal_and_the_rate_metrics_keep_theirs():
    """> **MARC, v18:** *"Don't use decimal points when displaying Yards … Exception is YDS/CARRY
    > (#.#)"*

    ✅ `fmt.precision_for` already encodes exactly this; the chart simply never asked it. The rule
    is keyed on the METRIC NAME, which is something the code can see.
    """
    yards = distribution.box(_tall_row(), width=420, show_value=False,
                             ticks=distribution.TICK_EXTREMES, metric="total_yards")
    # ⚠️ ASSERTED ON THE EXTRACTED LABELS, not on a substring of the markup: `"57" in svg` is true
    # of any coordinate that happens to contain those digits, which is R-859's class in a test.
    labels = _label_texts(yards)
    assert labels == ["57", "856", "256", "475"], labels
    assert not any("." in text for text in labels), labels
    # 🚨 AND THE RATES MUST NOT BE COLLATERAL — the two the 0-default would have flattened.
    assert fmt.precision_for("offense_explosiveness") == 2
    assert fmt.precision_for("offense_power_success") == 1
    assert fmt.precision_for("offense_success_rate") == 1
    assert fmt.precision_for("total_yards") == 0


def test_the_value_label_leaves_the_axis_row_only_when_asked():
    """A145's rule: the capability ships, the default does not move.

    📊 The move is what buys the axis labels their room — measured on 846 published rows at the
    240px one-sided call site, all four survive on 70.8% today and 99.1% with the value moved.
    """
    row = _tall_row()
    before = distribution.box(row, width=240, height=56, value=367.0,
                              ticks=distribution.TICK_EXTREMES, metric="total_yards")
    after = distribution.box(row, width=240, height=56, value=367.0,
                             ticks=distribution.TICK_EXTREMES, metric="total_yards",
                             value_labels_own_row=True)
    assert _svg_height(after) > _svg_height(before), "the value needs a row of its own"
    assert f"font-size='{distribution.VALUE_LABEL_FONT:g}'" in after, "the value label is not larger"
    assert f"font-size='{distribution.VALUE_LABEL_FONT:g}'" not in before, (
        "the default must not enlarge anything")


# ── A155: THE BYTE-IDENTITY PROOF, INVERTED ─────────────────────────────────────────────────
#
# 🚨 EVERY PREVIOUS CHANGE TO THIS MODULE SHIPPED A CAPABILITY AND PROVED NOTHING MOVED. Marc's
# v19 asks for the opposite: the serif is 50% taller on EVERY chart, globally, exactly as v18's
# darkening was. ✅ So the proof inverts — not *nothing moved*, but *ONLY the serif moved*.
#
# ⚠️ AND IT IS NOT CIRCULAR, WHICH IS THE OBJECTION WORTH ANSWERING. The constant could reach the
# viewBox, the rect, the median's span, the label placer's collision arithmetic or the frame — it
# is multiplied by `height` and nothing in the signature stops it propagating. The test flips it
# back and diffs the WHOLE string, so any leak anywhere shows up as a difference that is not a
# serif y.
#
# 🚨 THE CROSS-COMMIT HALF CANNOT LIVE HERE and saying so is the point (the note on
# `test_the_default_height_renders_the_same_bytes_as_before_the_parameter` above says why): the
# real comparison needs `distribution.py` at `d9c8caf` imported alongside this one, and the report
# carries that measurement. This carries the PROPERTY, which is the half CI can run.

def _without_serifs(svg: str) -> str:
    """Everything but the whisker caps.

    🚨 KEYED ON `y1 != y2`, NOT ON THE STROKE ATTRIBUTES, and this round got it wrong once before
    getting it right. The whisker's own HORIZONTAL RULE carries the identical `stroke-width='1'`
    and `opacity`, so a pattern matching only those strips the rule out of BOTH sides — which
    flatters the comparison by removing content it should be checking, and divides by zero the
    moment anything asks that content how tall it is.
    """
    return _SERIF_LINE.sub(lambda m: "" if m.group(2) != m.group(3) else m.group(0), svg)


_SERIF_LINE = re.compile(r"<line x1='([\d.-]+)' y1='([\d.-]+)' x2='[\d.-]+' y2='([\d.-]+)'"
                         r" stroke='currentColor' stroke-width='1' opacity='0\.6875'></line>")


def _serif_ys(svg: str):
    """The serif's two y coordinates: the vertical whisker caps, and only those.

    ⚠️ `y1 != y2` IS LOAD-BEARING — it excludes the whisker's own horizontal rule, whose `x1` is
    the same whisker end. Counting that would make every figure here twice what it should be, and
    it is the mistake this round made once against the live page before catching it.
    """
    out = []
    for x1, y1, y2 in re.findall(
            r"<line x1='([\d.-]+)' y1='([\d.-]+)' x2='[\d.-]+' y2='([\d.-]+)'"
            r" stroke='currentColor' stroke-width='1' opacity", svg):
        if y1 != y2 and float(y1) > 0:
            out.append((x1, y1, y2))
    return out


def test_the_serif_is_the_only_thing_that_moved(monkeypatch):
    """🚨 ACCEPTANCE 4. Across the parameter space, flipping the ratio back to 5/26 changes the
    serif's two y coordinates and NOTHING ELSE.

    ✅ THE CORPUS IS THE ONE THE HEIGHT TEST USES, plus the three A154 parameters that did not
    exist when that corpus was written — because a proof taken over a subset of the callers is a
    proof about that subset (R-843's family: an anchor has to come from the population under test).
    """
    compared = 0
    for width in (118, 240, 420):
        for height in (None, 56):
            for ticks in (distribution.TICK_PERCENTILES, distribution.TICK_EXTREMES,
                          distribution.TICK_NONE):
                for outliers in (False, True):
                    for extras in ({},
                                   {"extreme_lines": True},
                                   {"value_labels_own_row": True},
                                   {"metric": "total_yards"}):
                        for below in ({}, {"value_below": 90.0}):
                            kw = dict(value=367.0, width=width, height=height, ticks=ticks,
                                      outliers=outliers, label="T", **extras, **below)
                            new = distribution.box(_tall_row(), **kw)
                            with monkeypatch.context() as patch:
                                patch.setattr(distribution, "_SERIF_HALF_RATIO",
                                              5.0 / distribution.BOX_HEIGHT)
                                old = distribution.box(_tall_row(), **kw)
                            compared += 1
                            if new == old:
                                # A degenerate row draws no serif at all; that is not a leak.
                                assert _serif_ys(new) == [], f"{kw}: identical yet serifs drawn"
                                continue
                            # Strip the serif lines from both and the remainder must be equal.
                            assert _without_serifs(new) == _without_serifs(old), (
                                f"{kw}: something OTHER than the serif moved")
                            # 🚨 AND THE COUNT, because stripping alone would also pass if the
                            # serif had VANISHED — a different claim from "only the serif moved".
                            assert len(_serif_ys(new)) == len(_serif_ys(old)) > 0, kw
                            # And the serifs that did move, moved to 50% taller about the middle.
                            for (_x, ny1, ny2), (_ox, oy1, oy2) in zip(_serif_ys(new),
                                                                       _serif_ys(old)):
                                mid = (float(oy1) + float(oy2)) / 2
                                assert abs((float(ny2) - float(ny1))
                                           - 1.5 * (float(oy2) - float(oy1))) < 0.11, kw
                                assert abs((float(ny1) + float(ny2)) / 2 - mid) < 0.11, (
                                    f"{kw}: the serif grew off-centre")
    assert compared == 3 * 2 * 3 * 2 * 4 * 2, compared


def test_the_serif_now_outranks_the_box_rect(monkeypatch):
    """🚨 THE HIERARCHY INVERSION, AS AN ASSERTION — the thing Marc has not seen.

    ⚠️ IT IS THE CONSEQUENCE RATHER THAN THE REQUEST, so it is pinned separately: v19 asked for
    50% and this is what 50% does to the picture. If a later round tunes the number, THIS is the
    test that should make it think.
    """
    svg = distribution.box(_tall_row(), width=420, value=367.0)
    _y, rect_h = _rect(svg)
    serifs = _serif_ys(svg)
    assert serifs, "no serif drawn — the corpus is wrong, not the chart"
    serif_h = float(serifs[0][2]) - float(serifs[0][1])
    assert serif_h == 15.0, f"7.5/26 of a 26px band, both ends: {serif_h}"
    assert rect_h == 14.0, f"the rect is unchanged at 7/26: {rect_h}"
    assert serif_h > rect_h, (
        "A155 inverted the hierarchy deliberately: the whisker ends are now the taller mark. "
        "If this went red, the serif ratio moved back below the rect's and Marc's v19 is undone.")
