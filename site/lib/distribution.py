"""ONE PICTURE, THREE ENTRY POINTS. The standard way cfdb draws a distribution.

Marc: *"I want to have a standard way of showing. A good starting point for that method is in
`plot_distribution`."* — and *"It will be reusable call from several pages."* — and, for the
third, *"For every measure I'd like a horizontal box-whisker plot under the measure value."*

So: one module, three entry points over the SAME row, and no page owns any of them.

    thumbnail(row)  ->  inline SVG, ~120x28, for a header bar
    panel(row)      ->  the full layout, for a page with room
    box(row)        ->  a horizontal box-and-whisker, sized to the cell it is given

⚠️ THIS HEADER SAID "TWO SIZES" AND "two entry points" FOR A FULL ROUND AFTER `box()` SHIPPED —
R-821, and the file's own rule is four paragraphs down in R-562's correction: "Left uncorrected
this would have been a fresh instance of the failure this project keeps paying for: a
justification that stays in the file after it stops being true." It was the same failure, in the
same file, against the same paragraph.

⚠️ AND `box()` READS NO BIN COLUMNS, which is what lets it draw all three sibling views.
`thumbnail` and `panel` draw the HISTOGRAM and need `bin_min`, `bin_incr` and `bin_counts`;
a box plot is percentiles and whiskers, which every sibling publishes.

ONE RENDERER, NOT TWO. An earlier draft had the thumbnail as inline SVG and the panel as
Vega-Lite. That is two implementations of one picture, which is the thing the bin edges are
fixed to prevent: two renderers drift, and the day they disagree the reader cannot tell which
is lying. The panel is the thumbnail with more room — same geometry, same code path, more
pixels — so a bug in the bars is one bug and a fix is one fix.

NO CHART LIBRARY HERE, AND THAT IS STILL THE RIGHT CALL FOR THIS PICTURE. Ten bars is about
a dozen `<rect>` elements, and the cards already emit raw HTML on every row, so this is a
different string in a path that already exists — against a chart library it would be a
dependency, a spec, and a render pass for a thumbnail 28 pixels tall.

⚠️ R-562 CORRECTED THIS PARAGRAPH. It used to read "the site image's dependencies are
streamlit, sqlalchemy, psycopg2-binary, pandas, python-dotenv and openpyxl — no matplotlib, no
altair, no plotly". THE ALTAIR HALF WAS NEVER TRUE: `altair` is a HARD REQUIREMENT of
streamlit and has been in the image since the first build. `st.line_chart` is documented as
"syntax-sugar around st.altair_chart", so every chart the site has ever drawn through
streamlit went through Altair. `today.py` now imports it directly for the poll bump chart —
the one thing it needs, an inverted rank axis, is `alt.Scale(reverse=True)` and is not
reachable through `st.line_chart` at all — and it is declared in site/requirements.txt.

Left uncorrected this would have been a fresh instance of the failure this project keeps
paying for: a justification that stays in the file after it stops being true.

THE GEOMETRY COMES FROM THE ROW. `bin_min`, `bin_incr` and `bin_count` travel on the serving
row precisely so the renderer needs no lookup table and no knowledge of which metric it is
drawing. Hand it a row, get a picture.
"""
from typing import Optional

import pandas as pd
import streamlit as st

from lib import fmt

# The site's own accent, reused rather than a new palette. Bars are drawn in `currentColor` at
# reduced opacity so they inherit the theme and need no light/dark variant — the same trick
# R-141's indicators use.
BAR_OPACITY = 0.45
MEDIAN_OPACITY = 0.95

THUMBNAIL_HEIGHT = 28
PANEL_HEIGHT = 120

# A bar this tall is drawn for an empty bin, so a run of zeros reads as "measured and empty"
# rather than as a gap where the chart stopped. One pixel, deliberately.
EMPTY_BIN_PIXELS = 1


def parse_bin_counts(value) -> list:
    """The delimited string from the serving row, as integers.

    The counts cross the layer as `'0,3,9,25,15,1,0,0,0,0'` rather than as an array because
    this project dispatches the same models onto Postgres and Databricks, whose array types
    and aggregates differ, and it has one portability macro layer rather than two.

    A NULL here is not an empty histogram — it means the join found no bin rows, which is a
    defect upstream rather than a week with no games. Returning `[]` lets the caller tell the
    difference, because a week with no games has no ROW at all.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    out = []
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(int(float(piece)))
        except ValueError:
            # A malformed count is a defect, not a zero. Drawing a zero would hide it.
            return []
    return out


def _value_to_x(value, row, width: float) -> Optional[float]:
    """Where a value sits along the axis, in pixels, or None if it is off the end.

    The axis is the BIN RANGE, not the observed range — that is what makes two weeks
    comparable, and it is why a median outside the bins is clamped away rather than drawn at
    the edge as if it were inside.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    low, high = float(row["bin_min"]), float(row["bin_max"])
    if high <= low:
        return None
    position = (float(value) - low) / (high - low)
    if position < 0 or position > 1:
        return None
    return position * width


def _bars(counts: list, width: float, height: float) -> str:
    """The histogram itself. Shared by both sizes."""
    if not counts:
        return ""
    tallest = max(counts) or 1
    slot = width / len(counts)
    # A hairline gap so adjacent bars read as separate bins at 12px wide. Below about 3px of
    # slot the gap costs more than it buys, so it scales.
    gap = min(1.0, slot * 0.12)
    parts = []
    for index, count in enumerate(counts):
        tall = (count / tallest) * height if tallest else 0
        tall = max(tall, EMPTY_BIN_PIXELS)
        parts.append(
            f"<rect x='{index * slot + gap / 2:.2f}' y='{height - tall:.2f}' "
            f"width='{max(slot - gap, 0.5):.2f}' height='{tall:.2f}' "
            f"fill='currentColor' fill-opacity='{BAR_OPACITY if count else 0.18:.2f}'/>")
    return "".join(parts)


def _median_tick(row, width: float, height: float) -> str:
    x = _value_to_x(row.get("p50"), row, width)
    if x is None:
        return ""
    return (f"<line x1='{x:.2f}' y1='0' x2='{x:.2f}' y2='{height:.2f}' "
            f"stroke='currentColor' stroke-opacity='{MEDIAN_OPACITY}' stroke-width='1.5'/>")


def describe(row) -> str:
    """The tooltip. Same convention the result strip uses — every mark carries its own words.

    Carries the DENOMINATOR, always. A distribution over 9 games looks identical to one over
    124 and reports a different claim, which is why `n` is on the row at all (AC-G.33).

    🚨 THE DENOMINATOR'S COLUMN NAME DIFFERS BY GRAIN, AND THIS FUNCTION USED TO ASSUME ONE OF
    THEM. `row['games_in_week']` raised `KeyError` the first time `box()` was handed a row from
    `srv_game_team_metric_distribution`, whose denominator is `team_games_in_week` because its
    observations are team-games. `srv_team_week_metric_distribution` calls it `teams_in_week` for
    the same reason.

    ✅ SO THE LOOKUP IS BY CANDIDATE AND THE NOUN FOLLOWS IT. That is what makes one module able
    to describe all three siblings — Marc's "consistent method... applied to the all/subset of
    the population" — and the alternative was three describe() functions that would drift.
    ⚠️ The candidates are ordered most-specific first so a model publishing two of them cannot be
    described by the wrong one.
    """
    if row is None:
        return "cfdb holds no distribution for this week yet"
    denominators = (("team_games_in_week", "team-games"),
                    ("teams_in_week", "teams"),
                    ("games_in_week", "games"))
    bits = []
    for key, noun in denominators:
        total = row.get(key)
        if total is not None and not pd.isna(total):
            bits.append(f"n={int(row['n'])} of {int(total)} {noun}")
            break
    else:
        # 🚨 A145. THE FOURTH SIBLING PUBLISHES NO DENOMINATOR, AND `weeks_counted` IS NOT ONE.
        #
        # A143 built `srv_game_team_metric_distribution_through_prior_week` over a CUMULATIVE
        # window and deliberately shipped no second count: its own header says `n` IS the number
        # of team-games, because the window is built from observations, so a denominator column
        # would be the same number twice under two names. ✅ That reasoning is right and stands.
        #
        # ⚠️ SO THE TOOLTIP LOST ITS NOUN — `n=370` where the siblings say `n=172 of 172
        # team-games` — and B118, B119 and B120 each reported it. A145's prompt proposed adding
        # `("weeks_counted", "weeks")` to the list above.
        #
        # 🚨 THAT WOULD HAVE PRINTED `n=370 of 2 weeks`, WHICH IS NOT A SMALLER VERSION OF THE
        # RIGHT ANSWER — IT IS A FALSE RATIO. `n` counts team-games and `weeks_counted` counts
        # weeks; they are not numerator and denominator, and "370 of 2" reads as a fraction that
        # cannot be one. **A span is not a denominator, and the format string is what decides
        # which this column becomes.**
        #
        # ✅ SO IT IS A SEPARATE CLAUSE WITH ITS OWN PREPOSITION. `n=370 over 2 weeks` says the
        # thing a reader of a cumulative box actually needs — AC-G.33's rule that the denominator
        # travels with the numerator, honouring what this relation's denominator really is.
        span = row.get("weeks_counted")
        if span is not None and not pd.isna(span):
            weeks = int(span)
            bits.append(f"n={int(row['n'])} over {weeks} week{'' if weeks == 1 else 's'}")
        else:
            bits.append(f"n={int(row['n'])}")
    for label, key in (("p25", "p25"), ("median", "p50"), ("p75", "p75")):
        value = row.get(key)
        if value is not None and not pd.isna(value):
            bits.append(f"{label} {fmt.number(float(value), dp=1)}")
    # 🚨 A142. THE WHISKERS LOOK LIKE THE RANGE AND ARE NOT, AND UNTIL NOW NOTHING SAID SO.
    # `whisker_low`/`whisker_high` are Tukey's — the most extreme observation still inside
    # 1.5*IQR — so a week carrying one 800-yard game draws exactly like a week that does not.
    # 📊 2026 regular week 2 `total_yards` at game grain: whisker_high 690, max_value 856, two
    # observations outside. All three numbers are published and the reader was shown none of them.
    # ⚠️ THE EXTREMES RIDE WITH THE COUNT rather than being a second sentence, because "2 outliers"
    # answers *is this week unusual* and "to 856.0" answers *by how much* — and the second is the
    # question a reader who noticed the first will ask.
    outliers = row.get("outlier_count")
    if outliers is not None and not pd.isna(outliers) and int(outliers) > 0:
        span = [row.get("min_value"), row.get("max_value")]
        reach = ("" if any(v is None or pd.isna(v) for v in span)
                 else f" ({fmt.number(float(span[0]), dp=1)} to {fmt.number(float(span[1]), dp=1)})")
        bits.append(f"{int(outliers)} beyond the whiskers{reach}")
    if not row.get("is_locked", False):
        live = int(row.get("games_live") or 0)
        if live:
            bits.append(f"{live} game(s) still to kick off — this can still move")
    as_of = row.get("as_of_date")
    if as_of is not None and not pd.isna(as_of):
        bits.append(f"as of {as_of}")
    return " · ".join(bits)


def thumbnail(row, label: str = "", width: int = 120) -> str:
    """A sparkline-sized distribution, for a header bar.

    RESERVES ITS WIDTH WHETHER OR NOT THERE IS A ROW. R-141's lesson: an element that appears
    only when populated shifts everything beside it the moment a week is half-priced. A week
    with no row draws an empty box of the same size, so the band never reflows.
    """
    height = THUMBNAIL_HEIGHT
    if row is None:
        body = (f"<span class='cfdb-dist cfdb-dist-empty' style='width:{width}px' "
                f"title='cfdb holds no distribution for this week yet'>"
                f"<span class='cfdb-dist-label'>{label}</span>"
                f"<span class='cfdb-dist-none'>–</span></span>")
        return body

    counts = parse_bin_counts(row.get("bin_counts"))
    median = row.get("p50")
    median_text = fmt.number(float(median), dp=1) if median is not None and not pd.isna(median) \
        else "–"
    svg = (f"<svg class='cfdb-dist-svg' viewBox='0 0 {width} {height}' "
           f"width='{width}' height='{height}' preserveAspectRatio='none' aria-hidden='true'>"
           f"{_bars(counts, width, height)}{_median_tick(row, width, height)}</svg>")
    return (f"<span class='cfdb-dist' title='{describe(row)}'>"
            f"<span class='cfdb-dist-label'>{label}</span>{svg}"
            f"<span class='cfdb-dist-median'>{median_text}</span></span>")


def panel(row, label: str = "", width: int = 420) -> str:
    """The same picture with room to read it: the histogram, the box-and-whisker beneath it on
    a SHARED X-SCALE, and the statistics as a table beside it.

    The stats block is a table, not a caption — label left, value right, monospace — which is
    what `plot_distribution` does and is the part that makes the numbers scannable.
    """
    if row is None:
        return ("<div class='cfdb-dist-panel cfdb-dist-empty'>"
                "cfdb holds no distribution for this week yet.</div>")

    counts = parse_bin_counts(row.get("bin_counts"))
    hist_height = PANEL_HEIGHT
    box_height = PANEL_HEIGHT // 4

    # THE BOX SITS ON THE HISTOGRAM'S OWN SCALE. Drawn in one SVG rather than two stacked, so
    # the axes cannot drift apart — which is the same reason the thumbnail and this share
    # `_bars`.
    box = []
    q1 = _value_to_x(row.get("p25"), row, width)
    q3 = _value_to_x(row.get("p75"), row, width)
    lo = _value_to_x(row.get("whisker_lo"), row, width)
    hi = _value_to_x(row.get("whisker_hi"), row, width)
    mid = hist_height + box_height / 2
    if lo is not None and hi is not None:
        box.append(f"<line x1='{lo:.1f}' y1='{mid:.1f}' x2='{hi:.1f}' y2='{mid:.1f}' "
                   f"stroke='currentColor' stroke-opacity='.6'/>")
        for end in (lo, hi):
            box.append(f"<line x1='{end:.1f}' y1='{mid - 4:.1f}' x2='{end:.1f}' "
                       f"y2='{mid + 4:.1f}' stroke='currentColor' stroke-opacity='.6'/>")
    if q1 is not None and q3 is not None:
        box.append(f"<rect x='{q1:.1f}' y='{hist_height + 2:.1f}' "
                   f"width='{max(q3 - q1, 1):.1f}' height='{box_height - 4}' "
                   f"fill='currentColor' fill-opacity='.22' stroke='currentColor' "
                   f"stroke-opacity='.55'/>")
    median_x = _value_to_x(row.get("p50"), row, width)
    if median_x is not None:
        box.append(f"<line x1='{median_x:.1f}' y1='{hist_height + 2:.1f}' "
                   f"x2='{median_x:.1f}' y2='{hist_height + box_height - 2:.1f}' "
                   f"stroke='currentColor' stroke-width='2'/>")

    svg = (f"<svg class='cfdb-dist-svg' viewBox='0 0 {width} {hist_height + box_height}' "
           f"width='100%' height='{hist_height + box_height}' preserveAspectRatio='none' "
           f"aria-hidden='true'>{_bars(counts, width, hist_height)}"
           f"{_median_tick(row, width, hist_height)}{''.join(box)}</svg>")

    stats = []
    for name, key in (("n", "n"), ("min", "min_value"), ("p25", "p25"), ("median", "p50"),
                      ("p75", "p75"), ("max", "max_value")):
        value = row.get(key)
        shown = "–" if value is None or pd.isna(value) else (
            f"{int(value)}" if key == "n" else fmt.number(float(value), dp=1))
        stats.append(f"<div class='cfdb-dist-stat'><span>{name}</span><b>{shown}</b></div>")

    # THE SUBTITLE CARRIES THE BIN CONFIGURATION, as plot_distribution's does, so the picture
    # is reproducible from what is on screen.
    subtitle = (f"n={len(counts)} bins · incr={fmt.number(float(row['bin_incr']), dp=1)} · "
                f"min={fmt.number(float(row['bin_min']), dp=0)} · "
                f"max={fmt.number(float(row['bin_max']), dp=0)}")
    tails = []
    if int(row.get("below_min_count") or 0):
        tails.append(f"{int(row['below_min_count'])} below")
    if int(row.get("above_max_count") or 0):
        tails.append(f"{int(row['above_max_count'])} above")
    tail_note = f" · {' and '.join(tails)} the axis" if tails else ""

    return (f"<div class='cfdb-dist-panel' title='{describe(row)}'>"
            f"<div class='cfdb-dist-head'><b>{label}</b>"
            f"<span class='cfdb-dist-sub'>{subtitle}{tail_note}</span></div>"
            f"<div class='cfdb-dist-body'>{svg}"
            f"<div class='cfdb-dist-stats'>{''.join(stats)}</div></div></div>")


# ── box() ───────────────────────────────────────────────────────────────────────────────────
#
# Marc, 2026-09-14: "For every measure I'd like a horizontal box-whisker plot under the measure
# value. Span the full width of the cell. label upper/lower boundaries... annotate .25, .75.
# Bold line for .50. Blue line with label for Metric Value. Make it easy to configure. I want to
# set labels, tick mark strategy, etc"

# THE VALUE MARKER'S COLOUR, and it is only half of the marker — see `_value_marker`.
VALUE_COLOR = "#2f6fdb"

# TICK STRATEGIES, offered rather than invented. Marc asked to "set tick mark strategy"; these
# are the three the published row can actually support, and `percentiles` is the default because
# it is the only one whose ticks are values the row already carries — the other two derive
# positions the data never named.
TICK_PERCENTILES = "percentiles"   # p25, p50, p75 — the box's own edges
# TICK_BOUNDS draws the whisker ends only — what Marc called "upper/lower boundaries".
TICK_BOUNDS = "bounds"
TICK_NONE = "none"

BOX_HEIGHT = 26

# ── WHAT A TALLER BOX SCALES, AND WHAT IT MUST NOT ──────────────────────────────────────────
#
# A145, cfdb-main-R-992. Marc, v16: *"The circles need to be overlayed on top of the Box-Whisker
# with same x and y-axis. **The box-whisker will have to be taller** to accommodate the circles
# that will cover full regular season schedule (even with 50% overlap)."*
#
# 🚨 A TALLER BOX IS NOT A PROPORTIONALLY BIGGER BOX, AND THE TWO HALVES OF THAT SENTENCE HAVE
# DIFFERENT ANSWERS:
#
#     the x axis   CARRIES DATA. Every x on this chart is a value through `_box_scale`, and
#                  nothing here touches it — the height parameter cannot move a number sideways.
#     the y axis   CARRIES NOTHING. A box plot has no y quantity: the rule sits at the middle
#                  because it has to sit somewhere, and the box's THICKNESS is decoration.
#
# ✅ SO THE VERTICAL FURNITURE SCALES AND NO MEASUREMENT DOES. The box rect and the whisker
# serifs keep their PROPORTION of the band — which is what makes a 56px chart read as the same
# picture as a 26px one rather than as a thin rule stranded in a tall box.
#
# 🚨 AND THE ALTERNATIVE WAS RENDERED BEFORE IT WAS REJECTED — BY HOLDING THESE TWO RATIOS, NOT BY
# EDITING THE OUTPUT, because a picture that argues against a design has to BE the design rather
# than a rendering bug. `claude_work/renders/A145_what_a_taller_box_scales.png`, four bands.
#
# ⚠️ AND THE RASTER MADE A NARROWER CASE THAN THIS COMMENT FIRST CLAIMED, SO THE CLAIM MOVED.
# **Neither version contains the circles**, and it was wrong to imply the scaled one does: at
# height 56 the rect is 30.2px against a 56px stack, so marks extend past it either way. **That is
# correct behaviour** — the rect marks p25..p75 on the X axis and has no vertical meaning to
# contain anything with.
#
# ✅ THE ARGUMENT THAT SURVIVES IS CONSISTENCY, AND IT IS ENOUGH ON ITS OWN: a 26px box elsewhere
# on the page and a 56px box here should read as the same species of chart. Holding the rect at a
# literal 14px makes the taller one a thin slab stranded in a tall band — legible, but visibly a
# different picture. Scaling keeps the proportions, so height becomes a size rather than a
# redesign.
#
# ⚠️ THE RATIOS ARE DERIVED FROM THE EXISTING CONSTANTS RATHER THAN RETYPED, so the default is
# byte-identical by construction rather than by a test that happens to agree:
#
#     _RECT_HALF_RATIO   7 / 26   the box rect's half-thickness
#     _SERIF_HALF_RATIO  5 / 26   the whisker serif's half-height
#
# At `height=BOX_HEIGHT` these return exactly 7.0 and 5.0 and every emitted string is unchanged.
_RECT_HALF_RATIO = 7.0 / BOX_HEIGHT
_SERIF_HALF_RATIO = 5.0 / BOX_HEIGHT

# ── HOW WIDE IS A LABEL, REALLY ─────────────────────────────────────────────────────────────
#
# 🚨 A133. THE PLACER USED TO GUESS THIS TWICE OVER AND BOTH GUESSES WERE WRONG IN THE SAME
# DIRECTION. It modelled a label as `len(text) * 2.6` per half — "a 9px font averages ~5px a
# character" — and then discounted the result by a factor of 0.86 before comparing. A factor
# below 1.0 is a deliberate ALLOWANCE FOR OVERLAP, and this one permitted two 5-character
# labels to sit 22.36px apart when their ink needs 25.2px. The result was `180.0232.5` on the
# live site: two real numbers overprinted into a third that is neither, which is the exact
# defect A125's placement pass was built to prevent, surviving in a narrower gap.
#
# 📊 MEASURED IN CHROMIUM, `getComputedTextLength()` on a real <text> at font-size 9 in the
# font the page actually resolves — "Source Sans Pro", -apple-system, system-ui, … — because
# nothing in the DOM or in a character average can answer this:
#
#     0  5.844   1  4.344   2  5.609   3  5.812   4  5.969
#     5  5.734   6  5.906   7  5.297   8  5.922   9  5.906
#     .  2.844   -  4.422   ,  2.844   %  8.500   :  2.844   ' ' 2.703
#
# ⚠️ THE DIGITS ARE PROPORTIONAL, NOT TABULAR — `1` is 4.344 and `4` is 5.969, a 37% spread —
# so `len(text)` cannot work: `111.1` and `444.4` are the same length and differ by 7px. And
# `.` is 2.844 against the 5.2 the old model charged it, so a decimal was over-reserved while
# the whole label was under-reserved.
#
# ⚠️ `.cfdb-dist` SETS NO `font-family`, so the SVG inherits the page. If the site ever sets a
# font on this element these numbers must be re-measured; that is why the method is recorded
# rather than just the table.
_ADVANCE_9PX = {
    "0": 5.844, "1": 4.344, "2": 5.609, "3": 5.812, "4": 5.969,
    "5": 5.734, "6": 5.906, "7": 5.297, "8": 5.922, "9": 5.906,
    ".": 2.844, "-": 4.422, ",": 2.844, "%": 8.500, ":": 2.844, " ": 2.703,
}

# ⚠️ AN UNMEASURED CHARACTER IS CHARGED THE WIDEST THING IN THE TABLE. `value_label` takes
# arbitrary text from a caller, and erring wide DROPS a label where erring narrow OVERPRINTS
# one — and this whole section exists because the second is the worse failure.
_ADVANCE_FALLBACK = max(_ADVANCE_9PX.values())

# 🚨 ADDITIVE, NOT A MULTIPLIER, AND THE DIFFERENCE IS THE WHOLE BUG. `(half + other_half)` is
# already the exact condition for two ink boxes not to touch; anything wanted beyond it is
# CLEAR SPACE, which is a constant — two numbers need the same visual separation whether they
# read `7` or `-12.75`. A multiplier instead scales the allowance with the label, so it is most
# permissive exactly where the labels are longest and the crowding is worst.
LABEL_GAP = 2.0


def _text_width(text: str) -> float:
    """The rendered advance width of a label at font-size 9, summed per character."""
    return sum(_ADVANCE_9PX.get(ch, _ADVANCE_FALLBACK) for ch in text)


# The label band under the box — and, in two-value mode, an identical one above it.
LABEL_BAND = 15

# 🚨 A SENTINEL, BECAUSE `None` ALREADY MEANS SOMETHING ELSE HERE AND THE TWO CANNOT SHARE A
# SPELLING. `value_below=None` means *this side has no figure for this measure*, which is a real
# and common state; not passing `value_below` at all means *this is a one-value chart*. They draw
# differently and they must: with a second side declared, a lone away figure stays ABOVE the axis,
# because the side is what identifies the team. Collapsing them would put away's marker in the
# one-value centre position and silently tell the reader it was home's.
_UNSET = object()


# 🚨 THE WHISKER PAIR IS SPELLED TWO WAYS ACROSS THE THREE SIBLING VIEWS — R-820.
#
#     srv_week_metric_distribution        whisker_lo   whisker_hi
#     srv_team_week_metric_distribution   whisker_low  whisker_high
#     srv_game_team_metric_distribution   whisker_low  whisker_high
#
# ⚠️ A125 SHIPPED `box()` READING `whisker_low` ALONE, so the week-grain view — the oldest of the
# three and the only one with a histogram — fell through the guard four lines on and returned the
# EMPTY PLACEHOLDER. Measured at width 448: the working shape draws 1,605 characters with a rect,
# five lines and six labels; the `whisker_lo` shape returned 123 characters and ZERO elements,
# titled "this week has no distribution for that measure".
#
# 🚨 THAT IS THE WORST FAILURE AVAILABLE AND AN AC-G.11 VIOLATION: not a crash and not a blank, but
# a CONFIDENT WRONG ABSENCE — the page telling a reader the week has no distribution for a measure
# whose percentiles are sitting in the row it was just handed.
#
# ⚠️ AND `describe()` TWENTY LINES BELOW ALREADY CARRIED THE LESSON. It met the same seam on the
# DENOMINATOR (`games_in_week` / `teams_in_week` / `team_games_in_week`), and A125's fix was to look
# it up BY CANDIDATE with the noun following, because "the alternative was three describe()
# functions that would drift". THE DENOMINATOR GOT THE LESSON AND THE WHISKERS DID NOT.
#
# ✅ THE COLUMN IS NOT RENAMED, DELIBERATELY. `whisker_lo`/`whisker_hi` are PUBLISHED, so §3.3 makes
# that EXPAND -> MIGRATE -> CONTRACT across three rounds for a cosmetic consistency nobody outside
# this module has asked for. The reader's cost is zero either way; the renderer absorbs it.
#
# ⚠️ MEASURED ACROSS ALL THREE VIEWS BEFORE FIXING ONLY THIS ONE: 19 columns are common to all
# three — every percentile p02 through p98, `iqr`, `min_value`, `max_value`, `mean`, `stddev`, `n`,
# `outlier_count`, the keys and `as_of_ts`. The whiskers are THE ONLY same-concept-different-name
# divergence. Everything else that differs is genuinely grain-specific: the bin columns and the
# lock columns belong to the week view alone, the axis columns to the team-week view alone.
_WHISKER_NAMES = (("whisker_low", "whisker_high"), ("whisker_lo", "whisker_hi"))


def _whisker_pair(row):
    """The whisker ends, whichever of the two vocabularies the row speaks.

    ⚠️ ONE LOOKUP FOR THE PAIR, NOT TWO INDEPENDENT ONES. `lo` and `hi` must come from the SAME
    view's vocabulary: a row answering `whisker_low` and `whisker_hi` is not a row with an
    unusual spelling, it is a row nobody published — no view emits that combination — and
    averaging two conventions would draw a box from two different models' numbers.

    🚨 SO A MIXED ROW RAISES RATHER THAN DEGRADES. R-748's rule is assert upstream and degrade
    downstream, and this is neither half: it is a PROGRAMMING error, not a data condition. It
    cannot arrive from serving, so it can only arrive from a hand-built dict — and surfacing that
    in a test is the whole point. A silent half-answer here is how the original defect survived.
    """
    for lo_key, hi_key in _WHISKER_NAMES:
        has_lo, has_hi = lo_key in row, hi_key in row
        if has_lo and has_hi:
            return row.get(lo_key), row.get(hi_key)
        if has_lo != has_hi:
            raise ValueError(
                f"distribution row carries {lo_key if has_lo else hi_key} without its pair — "
                f"no serving view publishes that combination, so this row was built by hand")
    return None, None


def _box_scale(lo: float, hi: float, width: float, pad: float):
    """A closure mapping a value to an x offset inside the box plot.

    ⚠️ A COORDINATE TRANSFORM, NOT METRIC ARITHMETIC — §4.2.1, and the same note A122 put on the
    win-probability sparkline because the next reader will see a division in `site/` and reach
    for R-611. The test is how many CONSUMERS a number can have: this produces a pixel offset
    inside one <svg>, which nobody can cite, export or sort on. Every quantity with a reader —
    the percentiles, the whiskers, the value itself — arrives computed.
    """
    span = (hi - lo) or 1.0

    def at(value: float) -> float:
        return pad + (float(value) - lo) / span * (width - 2 * pad)

    return at


# ── HOVER: `<title>` SURVIVES STREAMLIT'S SANITISER, AND THAT IS A MEASUREMENT ──────────────
#
# Marc, 2026-09-16: *"Is there hover functionality in the charts?"*
#
# 📊 THE ANSWER HAS TWO HALVES AND THE FIRST ONE IS "ALREADY, ON THE WHOLE CHART". Every entry
# point in this module wraps its SVG in `<span class='cfdb-dist' title='{describe(row)}'>`, which
# is a native tooltip — measured on a real page in Chromium, one `.cfdb-dist` element carrying
# `n=120 of 120 team-games · p25 300.0 · median 377.0 · p75 448.0`.
#
# 🚨 WHAT WAS MISSING IS PER-MARK HOVER, and the reason to check rather than assume is in
# `table.py`: this codebase has already lost `onclick` to Streamlit's sanitiser. ✅ MEASURED IN A
# REAL BROWSER AGAINST A REAL `st.markdown(..., unsafe_allow_html=True)`: `<title>` SURVIVES, as a
# child of `<svg>`, of `<circle>`, of `<line>` and of `<g>` — four probes, four elements in the
# DOM, attributes intact. No JavaScript, no library, and nothing for the sanitiser to strip.
#
# ⚠️ SO THE MECHANISM IS A WRAPPER RATHER THAN A FEATURE. A caller supplies the words; this module
# owns only the escaping and the placement. B118's *"Week #, Opponent Rank, Name, Record, Final
# Score"* is four joins in the page's own query and is not this module's to compose (§4.2.1).
def _esc(text: str) -> str:
    """Markup-safe text for a `<title>`, which is ELEMENT CONTENT rather than an attribute.

    ⚠️ THE EXISTING `title='...'` ATTRIBUTES ARE NOT ROUTED THROUGH HERE AND THAT IS DELIBERATE:
    changing them would move bytes on every chart the site already draws, to fix nothing anybody
    has hit — `describe()` composes from numbers. New text comes from callers, so it is escaped.
    """
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _titled(body: str, title: Optional[str]) -> str:
    """A mark, with its own hover if it was given one.

    ⚠️ A `<g>` RATHER THAN A `<title>` INSIDE THE SHAPE, so this works for the composed marks —
    `_value_marker` returns a cap AND a rule, and a title has to cover both or the reader gets a
    tooltip on the triangle and nothing on the line under it.
    """
    if not title:
        return body
    return f"<g><title>{_esc(title)}</title>{body}</g>"


# ── THE OUTLIERS, WHICH ARE PUBLISHED AND HAVE NEVER BEEN DRAWN ─────────────────────────────
#
# 🚨 `min_value`, `max_value` AND `outlier_count` ARE ALL ON THE ROW AND THE CHART SHOWED NONE OF
# THEM. Marc asked to *"add the data points to also show the IQR whiskers"* — the whiskers already
# ARE the IQR fences (1.5*IQR, Tukey), so that half of the request is already shipped and a round
# that rebuilt them would have built nothing. What is genuinely absent is the tail.
#
# ⚠️ AN OPEN CIRCLE, AND AC-G.22 DECIDES THE SHAPE RATHER THAN TASTE. B116 measured that a BORDER
# does not survive greyscale; position and shape do. So the outlier is a ring — unfilled, which is
# the vocabulary Marc used for a single observation — and it sits OUTSIDE the whisker serif, where
# nothing else in this chart can be. It cannot be confused with the value marker (a weighted rule
# with a triangular cap) or the median (a bold rule), in colour or out of it.
#
# 🚨 IT WIDENS THE FRAME AND THAT IS THE POINT, NOT A SIDE EFFECT. The module's existing rule says
# an outlier pinned to the boundary "reads as 'at the extreme' when the truth is 'beyond it'".
# Drawing the extreme where it is means the box gets narrower; a reader who wanted to know the
# week had an 856 in it is being told exactly that, and the cost is visible rather than hidden.
# ⚠️ WHICH IS ALSO WHY IT IS OFF BY DEFAULT: every existing caller draws the same bytes as before.
OUTLIER_RADIUS = 3.2


def _outlier_marks(at, mid: float, lo: float, hi: float,
                   min_value, max_value, count) -> str:
    """Rings at the observed extremes, drawn only where they lie outside the whiskers.

    ⚠️ THE DRAW RULE IS GEOMETRIC, NOT `outlier_count > 0`, AND THE TWO ARE DIFFERENT QUESTIONS.
    A week with every outlier on the high side has `min_value == whisker_low`, and a ring drawn
    there would sit exactly on the serif claiming to be beyond it. The count narrates; the
    comparison decides what is drawn.
    """
    marks = []
    tail = f" — {int(count)} beyond the whiskers" if count else ""
    for value, end, side in ((min_value, lo, "lowest"), (max_value, hi, "highest")):
        if value is None or pd.isna(value):
            continue
        value = float(value)
        if (side == "lowest" and value >= end) or (side == "highest" and value <= end):
            continue
        ring = (f"<circle cx='{at(value):.1f}' cy='{mid:.1f}' r='{OUTLIER_RADIUS}' fill='none' "
                f"stroke='currentColor' stroke-width='1.2' opacity='.7'></circle>")
        marks.append(_titled(ring, f"{side} {fmt.number(value, dp=1)}{tail}"))
    return "".join(marks)


def _value_marker(x: float, height: float, color: str = VALUE_COLOR) -> str:
    """The reader's own value: a blue line WITH WEIGHT AND A CAP, not colour alone.

    🚨 AC-G.22, AND THIS PANEL HAS BEEN HERE BEFORE. B102 measured that the green and red marks
    were 1.8 luma apart and that only Marc's diamond separated them for a greyscale reader. A
    blue line on a grey box is the same trap: hue is the first thing to go.

    So the marker carries THREE signals, only one of which is colour — it is twice the weight of
    the median rule, it has a triangular cap no other element has, and it is blue. Rendered in
    greyscale the weight and the cap both survive.
    """
    cap = (f"<polygon points='{x - 3.2:.1f},0 {x + 3.2:.1f},0 {x:.1f},4.6' "
           f"fill='{color}'></polygon>")
    rule = (f"<line x1='{x:.1f}' y1='0' x2='{x:.1f}' y2='{height:.1f}' "
            f"stroke='{color}' stroke-width='2.2'></line>")
    return cap + rule


def _sided_marker(x: float, height: float, mid: float, above: bool, color: str) -> str:
    """One team's value, in its OWN HALF of the box, with its cap on the outside.

    🚨 POSITION IS THE ENCODING AND COLOUR IS DECORATION ON TOP — Marc asked for *"Away above the
    line, Home below"* and prefixed it *"would be ideal... if possible"*. **It is not a nicety, it
    is the accessibility answer**, and this is the AC-G.22 trap in its purest form: two team
    colours on one chart, and NOTHING PREVENTS TWO TEAMS BEING THE SAME RED. B102 measured green
    and red at 1.8 luma apart on this very panel, separated only by Marc's diamond; two brand
    hues can be closer than that. Above and below survive greyscale, colour-blindness, and two
    teams out of the same palette — hue survives none of them.

    ✅ AND IT ANSWERS A SECOND PROBLEM THE COLOUR COULD NOT, WHICH IS WHY IT IS THE RIGHT SHAPE
    RATHER THAN A PREFERENCE: two teams with the SAME figure put two markers at the SAME x.
    MEASURED on `srv_game_team` — **10.1% of the games that render this panel have at least one of
    its six rows tied** (372 of 3,674; `first_downs` alone ties in 4.74%). One game in ten, not a
    corner. Stacked in one lane those markers are one mark and the reader loses a team; in
    separate halves they cannot collide at all.

    The cap points INWARD at the axis from each side, so the two markers read as a mirrored pair
    rather than as two unrelated glyphs.
    """
    if above:
        cap = (f"<polygon points='{x - 3.2:.1f},0 {x + 3.2:.1f},0 {x:.1f},4.6' "
               f"fill='{color}'></polygon>")
        rule = (f"<line x1='{x:.1f}' y1='0' x2='{x:.1f}' y2='{mid:.1f}' "
                f"stroke='{color}' stroke-width='2.2'></line>")
    else:
        cap = (f"<polygon points='{x - 3.2:.1f},{height:.1f} {x + 3.2:.1f},{height:.1f} "
               f"{x:.1f},{height - 4.6:.1f}' fill='{color}'></polygon>")
        rule = (f"<line x1='{x:.1f}' y1='{mid:.1f}' x2='{x:.1f}' y2='{height:.1f}' "
                f"stroke='{color}' stroke-width='2.2'></line>")
    return cap + rule


def box(row, value=None, width: int = 240, label: str = "",
        ticks: str = TICK_PERCENTILES, show_value: bool = True,
        value_label: Optional[str] = None, dp: int = 1,
        value_color: Optional[str] = None,
        value_below=_UNSET, value_below_label: Optional[str] = None,
        value_below_color: Optional[str] = None,
        frame: Optional[tuple] = None, outliers: bool = False,
        value_title: Optional[str] = None,
        value_below_title: Optional[str] = None,
        height: Optional[int] = None) -> str:
    """A horizontal box-and-whisker for one measure, sized to the cell it is given.

    THE THIRD ENTRY POINT, over the SAME row as `thumbnail` and `panel`. One renderer, not two —
    the module's opening argument, and the reason it exists: "two renderers drift, and the day
    they disagree the reader cannot tell which is lying."

    ✅ AND IT WORKS OVER ANY OF THE THREE DISTRIBUTION VIEWS, which is Marc's "consistent method
    for evaluating how to present measures so that we can apply it to the all/subset of the
    population". `srv_week_metric_distribution` (game grain), `srv_team_week_metric_distribution`
    (team, cumulative) and `srv_game_team_metric_distribution` (team, single game) all publish
    the same percentile vocabulary, so this function needs no metric name and no lookup table.

    ⚠️ IT READS NO BIN COLUMNS. `thumbnail` and `panel` draw the histogram and need `bin_min`,
    `bin_incr` and `bin_counts`; a box plot is p25/p50/p75 and the whiskers. That is why the
    eighteen box-score measures could be published without eighteen hand-set bin ranges.

    Marc's specification, in his words, and where each part is:

        the box          p25 to p75
        the median       a BOLD line at p50 — 1.8 against the box's 1
        the whiskers     whisker_low to whisker_high, with both boundaries LABELLED
        the value        a BLUE line WITH A LABEL — and a cap and double weight, see AC-G.22
        the width        spans whatever cell width it is handed

    ⚠️ EVERY PARAMETER HAS A DEFAULT AND THE DEFAULTS ARE WHAT A CALLER GETS ON DAY ONE (§3
    rule 3.1). The call sites in `site/views/matchup.py` are session B's to write on B's own
    round; shipping the entry point without them is the rule, not an omission.

    ⚠️ TWO VALUES ON ONE CHART — Marc, 2026-09-14 (v10): *"make a single box-whisker chart...
    Populate the single chart with data points for both teams. Use team color to differentiate.
    Would be ideal to label Away above the line, Home below, if possible."*

    ✅ PASS `value_below` AND THE CHART BECOMES TWO-SIDED: `value` is drawn in the UPPER half with
    its label ABOVE the box, `value_below` in the LOWER half with its label BELOW. See
    `_sided_marker` for why position rather than hue is the primary encoding, and for the 10.1%
    of panels where the two figures collide.

    🚨 THE COLOUR ARRIVES COMPOSED AND IS NEVER COMPUTED HERE. `value_color` and
    `value_below_color` are CSS colour strings the caller has already resolved — in practice
    `light-dark(<on-light>, <on-dark>)`, which is what `matchup.py:_table_header` already builds
    from `identity.text_on`. **This module must not reach for a team colour**: `identity` owns
    that (§4.2.1), and R-855 is one round old — B109 found that the app's only precedent,
    `identity.text_on(row)` defaulting to the ON-LIGHT variant, rendered `rgb(0,0,0)` on a
    `rgb(14,17,23)` page, invisible, for the **18.6% of teams that publish `#000000` there.**
    Composing the pair a second time in here is exactly the drift that finding is about.

    ⚠️ A COLOUR OF `None` FALLS BACK TO `VALUE_COLOR`, which matters because **10.89% of games
    have a side with no sourced colour** (B109). The marker still draws, in the site accent.

    row                a distribution row, or None
    value              the figure for the measure, or None. Two-sided: the ABOVE side
    ticks              TICK_PERCENTILES (default) | TICK_BOUNDS | TICK_NONE
    show_value         draw the value marker(s) at all
    value_label        override the text at the marker; defaults to the formatted value
    dp                 decimals for every label
    value_color        CSS colour for the value marker; defaults to VALUE_COLOR
    value_below        the second side's figure. PASSING IT AT ALL selects two-sided mode —
                       `None` then means *this side has no figure*, and the other side still
                       draws in its own half rather than moving to the centre (see `_UNSET`)
    value_below_label  as `value_label`, for the below side
    value_below_color  as `value_color`, for the below side
    frame              `(lo, hi)` to widen the SCALE by — see below. Never narrows, never moves
                       a label, never changes a printed figure
    outliers           draw `min_value`/`max_value` as rings where they lie outside the whiskers.
                       OFF BY DEFAULT, so every existing caller renders the same bytes; on, it
                       widens the frame, which is the honest cost of showing the tail
    value_title        hover text for the value marker — a native SVG `<title>`, measured to
                       survive Streamlit's sanitiser. The words are the caller's (§4.2.1)
    value_below_title  as `value_title`, for the below side
    height             the plot band in pixels, default `BOX_HEIGHT`. The vertical furniture
                       scales with it and NO MEASUREMENT DOES — see the ratios above. A caller
                       overlaying marks inside the band asks for the height those marks need
    """
    if row is None:
        return (f"<span class='cfdb-dist cfdb-dist-empty' style='width:{width}px' "
                f"title='cfdb holds no distribution for this week yet'>\u2013</span>")

    def num(key):
        raw = row.get(key)
        return None if raw is None or pd.isna(raw) else float(raw)

    def as_number(raw):
        return None if raw is None or pd.isna(raw) else float(raw)

    p25, p50, p75 = num("p25"), num("p50"), num("p75")
    # See _whisker_pair: the three views spell this two ways and the column is not renamed.
    raw_lo, raw_hi = _whisker_pair(row)
    lo, hi = as_number(raw_lo), as_number(raw_hi)
    if None in (p25, p50, p75) or lo is None or hi is None:
        return (f"<span class='cfdb-dist cfdb-dist-empty' style='width:{width}px' "
                f"title='this week has no distribution for that measure'>\u2013</span>")

    # ⚠️ TWO-SIDED MODE IS SELECTED BY THE CALLER, NOT BY THE DATA. See `_UNSET`: a declared
    # second side with no figure still leaves the first one in its own half, because the half is
    # what says which team it belongs to.
    two_sided = show_value and value_below is not _UNSET

    def usable(candidate) -> bool:
        return candidate is not None and not pd.isna(candidate)

    # Each entry: (x-value, label override, colour, side). `side` is None for the one-value
    # chart, which keeps its full-height marker and its single label band unchanged.
    markers = []
    if show_value and usable(value):
        markers.append((float(value), value_label, value_color or VALUE_COLOR,
                        "above" if two_sided else None, value_title))
    if two_sided and usable(value_below):
        markers.append((float(value_below), value_below_label,
                        value_below_color or VALUE_COLOR, "below", value_below_title))

    # 🚨 `lo`/`hi` DRAW. `frame_lo`/`frame_hi` SCALE. THEY ARE TWO DIFFERENT THINGS AND THE
    # WHOLE OF A139's PART 1 LIVES IN THAT SEAM.
    #
    # ⚠️ THE FRAME INCLUDES THE VALUE, so a figure outside the whiskers is drawn where it is
    # rather than clamped to the edge. An outlier pinned to the boundary reads as "at the
    # extreme" when the truth is "beyond it", and the outlier is the interesting case.
    #
    # ⚠️ BOTH VALUES WIDEN IT. A frame built from one side would draw the other outside the
    # viewBox, which is the same clipping defect one layer over.
    frame_lo, frame_hi = lo, hi
    for marker_value, _label, _color, _side, _title in markers:
        frame_lo, frame_hi = min(frame_lo, marker_value), max(frame_hi, marker_value)

    # 🚨 A142. A RING DRAWN AT THE EXTREME HAS TO BE INSIDE THE viewBox, so the frame takes the
    # extremes the same way it takes the value markers — and for the same stated reason, which is
    # that clamping an outlier to the boundary tells the reader it is AT the extreme when it is
    # BEYOND it. ⚠️ ONLY WHEN `outliers` IS ON: an unasked-for widening would move every chart the
    # site already draws, which is the one thing a default may not do.
    out_min, out_max = (num("min_value"), num("max_value")) if outliers else (None, None)
    if out_min is not None:
        frame_lo = min(frame_lo, out_min)
    if out_max is not None:
        frame_hi = max(frame_hi, out_max)

    # 🚨 A139, cfdb-wta-R-927. `frame=(lo, hi)` PUTS TWO CHARTS ON ONE SCALE, and it is the
    # honest version of a thing B114 refused to fake from the page.
    #
    # 📊 THE DEFECT IT CLOSES, MEASURED BY B114 ON THE GAINED-OVER-ALLOWED PAIR: two `box()`
    # calls stacked vertically frame on their OWN whiskers, so on `total` the top row spans
    # 416.5 yards and the bottom row 366.0 across the same pixels — a 13.8% scale difference in
    # a layout that invites the reader to compare them by eye, with nothing on screen admitting
    # to it. On `rushing` the narrower row uses 70.8% of the wider one's range.
    #
    # ✅ IT WIDENS AND NEVER REPLACES, which is the property the comment above protects: a value
    # beyond the union is still drawn beyond it rather than clamped to the caller's bound. A
    # `frame` narrower than the data is therefore inert rather than wrong.
    #
    # ❌ AND IT TOUCHES NOTHING THAT PRINTS. `lo`/`hi` still draw the whisker rule, its serifs
    # and the boundary labels, so every figure on the chart stays this row's own figure. A
    # shared axis that relabelled the whiskers with the union's numbers would be telling the
    # reader this team's week ran from 142.5 when it ran from 204.0 — which is exactly the
    # dishonest version, and it is one line away from here.
    #
    # ⚠️ THE UNION IS A PROPERTY OF THE WEEK, NOT OF THE TWO ROWS ON SCREEN (R-590: every matchup
    # in a week is drawn on the same axes). This parameter only accepts it; the page computes it.
    if frame is not None:
        given_lo, given_hi = (as_number(frame[0]), as_number(frame[1]))
        if given_lo is not None:
            frame_lo = min(frame_lo, given_lo)
        if given_hi is not None:
            frame_hi = max(frame_hi, given_hi)

    pad = 10.0
    height = float(BOX_HEIGHT if height is None else height)
    mid = height / 2.0
    # See the ratios' note above: the furniture keeps its proportion, the data keeps its x.
    rect_half = height * _RECT_HALF_RATIO
    serif_half = height * _SERIF_HALF_RATIO
    at = _box_scale(frame_lo, frame_hi, width, pad)
    parts = []

    # The whisker rule, end to end, with serifs at the boundaries.
    parts.append(f"<line x1='{at(lo):.1f}' y1='{mid:.1f}' x2='{at(hi):.1f}' y2='{mid:.1f}' "
                 f"stroke='currentColor' stroke-width='1' opacity='.55'></line>")
    for end in (lo, hi):
        parts.append(f"<line x1='{at(end):.1f}' y1='{mid - serif_half:.1f}' x2='{at(end):.1f}' "
                     f"y2='{mid + serif_half:.1f}' stroke='currentColor' stroke-width='1' "
                     f"opacity='.55'></line>")

    # The box: p25 to p75.
    # ⚠️ THE HEIGHT IS EMITTED AT ZERO DECIMALS AND THE y AT ONE, WHICH IS NOT AN OVERSIGHT: it is
    # what the pre-A145 literal `height='14'` did, and keeping it is what makes the default render
    # byte-identical. A rect's thickness is decoration and a whole pixel is enough of it.
    parts.append(f"<rect x='{at(p25):.1f}' y='{mid - rect_half:.1f}' "
                 f"width='{max(at(p75) - at(p25), 1):.1f}' "
                 f"height='{rect_half * 2:.0f}' fill='currentColor' fill-opacity='.14' "
                 f"stroke='currentColor' stroke-width='1' stroke-opacity='.5'></rect>")

    # 🚨 THE MEDIAN IS BOLD — Marc said so explicitly, and it is the one line a reader looks for.
    # ⚠️ IT SPANS THE RECT RATHER THAN A CONSTANT, so it stays the box's own divider at any height.
    # A 1.8px rule that stopped 7px either side of centre in a 56px band would read as a tick.
    parts.append(f"<line x1='{at(p50):.1f}' y1='{mid - rect_half:.1f}' x2='{at(p50):.1f}' "
                 f"y2='{mid + rect_half:.1f}' stroke='currentColor' stroke-width='1.8' "
                 f"opacity='{MEDIAN_OPACITY}'></line>")

    # ⚠️ THE RINGS GO DOWN BEFORE THE VALUE MARKERS, so a team figure that happens to sit on the
    # week's own extreme draws ON TOP of the ring rather than under it. The reader's own number
    # outranks the week's furniture — the same precedence the label placer already applies.
    drawn_outliers = ""
    if outliers:
        drawn_outliers = _outlier_marks(at, mid, lo, hi, out_min, out_max,
                                        num("outlier_count"))
        parts.append(drawn_outliers)

    for marker_value, _label, marker_color, side, marker_title in markers:
        body = (_value_marker(at(marker_value), height, marker_color) if side is None
                else _sided_marker(at(marker_value), height, mid, side == "above", marker_color))
        parts.append(_titled(body, marker_title))

    # ── LABELS, IN ONE PLACEMENT PASS ────────────────────────────────────────────────────────
    #
    # 🚨 THE FIRST VERSION EMITTED EVERY LABEL AT ITS OWN x AND THE RASTER SHOWED WHY THAT FAILS.
    # Rendered at 2x, a value of 180 beside a median of 152 produced "152.080.0" — two real
    # numbers overprinted into a third that is not either of them — and a value past the upper
    # whisker ran off the right edge as "450.(". Both are legibility defects invisible in the
    # DOM: every <text> element was present and correct.
    #
    # ✅ SO LABELS ARE PLACED, NOT JUST EMITTED. Three rules, in order:
    #   1. THE VALUE LABEL WINS. It is the reader's own number and the only one they came for.
    #   2. A LABEL THAT WOULD COLLIDE IS DROPPED, not shrunk and not offset — a shifted label
    #      points at the wrong place on the axis, which is worse than one fewer label.
    #   3. EVERY LABEL IS CLAMPED INSIDE THE FRAME, with its anchor following, so nothing is
    #      clipped by the viewBox.
    #
    # ⚠️ THE BOUNDARY LABELS ARE MARC'S "label upper/lower boundaries" and are drawn for every
    # tick strategy except `none` — they are the frame's meaning rather than decoration, so they
    # are placed BEFORE the percentile ticks and only the value outranks them.
    # ✅ ONE BAND PER BASELINE, AND THIS IS WHERE THE ABOVE/BELOW LAYOUT PAYS FOR ITSELF TWICE.
    # Labels only collide with labels on the SAME baseline, so the above side's figure competes
    # with nothing at all and the below side inherits exactly the contest the one-value chart
    # already had. R-846 — the median's label being dropped whenever the value sits near it — is
    # therefore not made worse by the second value; measured across 120/200/300/448, the two-value
    # chart keeps MORE labels than the one-value chart at every width, because it adds a label in
    # a band where nothing can displace it.
    bands = {}

    def place(band: str, x: float, text: str, color: Optional[str] = None) -> None:
        # Half the label's MEASURED width each side is the exclusion zone — see _ADVANCE_9PX
        # for why this is summed per character rather than averaged over the length.
        half = _text_width(text) / 2.0
        x = min(max(x, pad + half - 8), width - pad - half + 8)
        placed = bands.setdefault(band, [])
        for other_x, other_half, _, _ in placed:
            # Touching boxes plus a constant of clear space. No multiplier: see LABEL_GAP.
            if abs(x - other_x) < half + other_half + LABEL_GAP:
                return
        placed.append((x, half, text, color))

    # THE VALUE LABEL WINS, so it is placed into its band before anything else can take the room.
    for marker_value, marker_label, marker_color, side, _title in markers:
        place("above" if side == "above" else "below", at(marker_value),
              marker_label if marker_label is not None
              else fmt.number(marker_value, dp=dp),
              marker_color)
    if ticks != TICK_NONE:
        place("below", at(lo), fmt.number(lo, dp=dp))
        place("below", at(hi), fmt.number(hi, dp=dp))
    if ticks == TICK_PERCENTILES:
        for edge in (p50, p25, p75):
            place("below", at(edge), fmt.number(edge, dp=dp))

    # ⚠️ THE BOX KEEPS ITS OWN COORDINATES AND THE BAND IS ADDED AROUND IT, so every line above
    # this point is written once and the one-value SVG is unchanged to the byte.
    top_band = LABEL_BAND if two_sided else 0
    for band, baseline in (("above", -6.0), ("below", height + 11)):
        for x, _half, text, color in bands.get(band, []):
            fill = f"fill='{color}'" if color else "fill='currentColor' opacity='.65'"
            parts.append(f"<text x='{x:.1f}' y='{baseline:.1f}' text-anchor='middle' "
                         f"font-size='9' {fill}>{text}</text>")

    body = "".join(parts)
    if top_band:
        body = f"<g transform='translate(0,{top_band})'>{body}</g>"
    # ⚠️ `:g` ON THE THREE PLACES THIS IS EMITTED, AND IT IS THE DIFFERENCE BETWEEN A
    # BYTE-IDENTICAL DEFAULT AND 580 CHANGED RENDERS. `height` became a float so the ratios above
    # could be computed from it, which turned `41` into `41.0` in the viewBox and both attributes
    # — the ONLY thing A145's first draft changed at the default, and the hash comparison against
    # the pre-change module is what found it. `:g` prints 41 for 41.0 and 71.5 for 71.5.
    total_height = top_band + height + 15

    # ⚠️ AC-G.11 — AN ABSENCE MUST SAY WHICH ABSENCE IT IS, AND A SCREEN READER GETS ONLY THIS
    # STRING. Two markers drawn and one marker drawn are different pictures; silently narrating
    # both as "box and whisker" would tell a reader the sides agree when one of them has no
    # figure at all. Sighted readers see the empty half; this is how everyone else does.
    #
    # The one-value chart's label is UNCHANGED — B108's live call site renders the same bytes.
    reading = f"{label or 'Distribution'}: box and whisker"
    # 🚨 AC-G.11 AGAIN, AND IT IS THE HALF A139 CAUGHT GOING THE OTHER WAY. A138's curve told a
    # screen-reader user which side the number belonged to and told a sighted reader nothing; this
    # is the mirror of it, so the rings do not become a mark only sighted readers can count.
    if outliers and drawn_outliers:
        count = num("outlier_count")
        reading += (f", {int(count)} beyond the whiskers" if count
                    else ", extremes beyond the whiskers")
    if two_sided:
        drawn = len(markers)
        reading += (", two values" if drawn == 2 else
                    ", one value — the other side has none" if drawn == 1 else
                    ", neither side has a value")
    svg = (f"<svg viewBox='0 0 {width} {total_height:g}' width='{width}' "
           f"height='{total_height:g}' "
           f"role='img' aria-label='{reading}' "
           f"style='display:block;max-width:100%'>{body}</svg>")
    return f"<span class='cfdb-dist' title='{describe(row)}'>{svg}</span>"


def render(html: str) -> None:
    """Write one of the above to the page."""
    st.markdown(html, unsafe_allow_html=True)
