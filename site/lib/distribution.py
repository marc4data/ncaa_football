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
import math
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


def axis_span(row, axis=None) -> Optional[tuple]:
    """The span this chart DRAWS: the caller's axis if it gave one, else the bin range.

    🚨 A237 (cfdb-main-R-3039). ONE PLACE DECIDES WHAT THE AXIS IS, because three things have to
    agree about it — the bars, the box and the ticks — and A235's whole reason for drawing them
    in one SVG was that they cannot be allowed to drift apart.
    """
    if axis is not None:
        low, high = float(axis[0]), float(axis[1])
    else:
        low, high = float(row["bin_min"]), float(row["bin_max"])
    return None if high <= low else (low, high)


def _value_to_x(value, row, width: float, axis=None) -> Optional[float]:
    """Where a value sits along the axis, in pixels, or None if it is off the end.

    ⚠️ THE DEFAULT AXIS IS THE BIN RANGE, not the observed range — that is what makes two weeks
    comparable, and it is why a median outside the bins is clamped away rather than drawn at
    the edge as if it were inside.

    🚨 A237 (cfdb-main-R-3039). `axis=` NARROWS IT, AND THAT IS A TRADE THE CALLER MAKES.
    > **MARC, 2026-09-25:** *"Constrain the box-whisker to just show the extent of the whiskers.
    > Don't need to include x-axis range to cover outliers beyond IQR."*
    📊 Measured on 2026 week 3: the three KPI charts were using **49%, 50% and 56%** of their own
    width, because the bin range is set wide enough to hold a season's tail. ⚠️ **What is given up
    is cross-week comparability** — the property the sentence above exists to protect — so a
    caller that narrows is choosing a readable picture of THIS week over a comparable one across
    weeks, and `today._kpi_chart` says in its own comment that it made that choice.

    ⚠️ **A VALUE OUTSIDE THE DRAWN AXIS STILL RETURNS None**, which is A142's law and is why the
    caller has to make the dropped mass visible rather than letting it clamp to the edge.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    span = axis_span(row, axis)
    if span is None:
        return None
    low, high = span
    position = (float(value) - low) / (high - low)
    if position < 0 or position > 1:
        return None
    return position * width


def _beyond_note(count: int, was_clamped: bool) -> str:
    """What the edge marker says it is marking, which is not always the same thing.

    ⚠️ AC-G.11 — AN ABSENCE MUST SAY WHICH ABSENCE IT IS. The same triangle now stands for two
    different facts: histogram mass that fell outside the drawn axis (A237's case), and a
    box-and-whisker mark that had to be clamped to the frame (A243's). A reader hovering it is
    entitled to know which, and "3 beyond the drawn axis" would be false when nothing was counted.
    """
    if count and was_clamped:
        return f"{int(count)} beyond the drawn axis, and the whisker reaches past it"
    if count:
        return f"{int(count)} beyond the drawn axis"
    return "the range reaches past the drawn axis"


def clamped_to_axis(value, row, width: float, axis=None):
    """Where a value sits, CLAMPED into the frame, plus which edge it was pushed to.

    Returns `(x, side)` — `side` is None when the value was already inside, `"lo"`/`"hi"` when it
    was not. `(None, None)` when the value is null or the axis is degenerate.

    🚨 A243 (cfdb-main-R-3321). THIS EXISTS BECAUSE A FIXED AXIS IS HOW A VALUE DISAPPEARS.
    `_value_to_x` returns None outside the frame, which is right when the caller can choose not to
    draw — but with a FIXED `(0, 80)` every mark beyond it would simply stop being drawn, and a
    whisker that is not drawn is the absence AC-G.11 forbids.

    ⚠️ TWO FAILURE MODES, BOTH WITH PRECEDENT IN THIS MODULE:
      1. drawn OUTSIDE the viewBox — A237's overflow arrow ran x=140 to 144.5 on a 140-wide box
         (cfdb-main-R-3037); the DOM said it was there and a raster said it was not;
      2. SILENTLY CLIPPED — the mark is absent and nothing says so.

    ✅ SO: clamp (never outside the frame) AND report the side (never silent). The caller marks the
    edge, which is what makes the clamp honest rather than a lie about where the value is — A142's
    law is that a mark at the boundary must not claim to BE the boundary, and the edge marker is
    what distinguishes "at 80" from "beyond 80".
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return (None, None)
    span = axis_span(row, axis)
    if span is None:
        return (None, None)
    low, high = span
    position = (float(value) - low) / (high - low)
    if position < 0:
        return (0.0, "lo")
    if position > 1:
        return (float(width), "hi")
    return (position * width, None)


def _bars(counts: list, width: float, height: float, bins=None, axis=None) -> str:
    """The histogram itself. Shared by both sizes.

    ⚠️ WITHOUT `bins`/`axis` THE BARS ARE SPREAD EVENLY ACROSS THE WIDTH, which is correct only
    because the axis IS the bin range — every bin gets the same slot because every bin is the
    same fraction of the axis. **That assumption is the whole of this function's old geometry**,
    and it stops being true the moment a caller narrows the axis (A237).

    🚨 SO WHEN AN AXIS IS GIVEN, EVERY BAR IS PLACED BY ITS OWN VALUE RANGE rather than by its
    index. `bins` is `(bin_min, bin_max)`; a bin entirely outside the drawn axis is SKIPPED, and
    one straddling the edge is CLIPPED to it — **and the caller is responsible for saying that
    mass went missing** (`_overflow_marks`). A bar silently squeezed to the edge would put mass
    at a value it does not have, which is A142's law applied to a rectangle.
    """
    if not counts:
        return ""
    tallest = max(counts) or 1
    parts = []

    if bins is None or axis is None:
        slot = width / len(counts)
        # A hairline gap so adjacent bars read as separate bins at 12px wide. Below about 3px of
        # slot the gap costs more than it buys, so it scales.
        gap = min(1.0, slot * 0.12)
        for index, count in enumerate(counts):
            tall = (count / tallest) * height if tallest else 0
            tall = max(tall, EMPTY_BIN_PIXELS)
            parts.append(
                f"<rect x='{index * slot + gap / 2:.2f}' y='{height - tall:.2f}' "
                f"width='{max(slot - gap, 0.5):.2f}' height='{tall:.2f}' "
                f"fill='currentColor' fill-opacity='{BAR_OPACITY if count else 0.18:.2f}'/>")
        return "".join(parts)

    bin_lo, bin_hi = float(bins[0]), float(bins[1])
    axis_lo, axis_hi = float(axis[0]), float(axis[1])
    if bin_hi <= bin_lo or axis_hi <= axis_lo:
        return ""
    incr = (bin_hi - bin_lo) / len(counts)
    scale = width / (axis_hi - axis_lo)
    gap = min(1.0, incr * scale * 0.12)
    for index, count in enumerate(counts):
        left, right = bin_lo + index * incr, bin_lo + (index + 1) * incr
        if right <= axis_lo or left >= axis_hi:
            continue
        x0 = max((left - axis_lo) * scale, 0.0)
        x1 = min((right - axis_lo) * scale, width)
        if x1 - x0 <= 0:
            continue
        tall = (count / tallest) * height if tallest else 0
        tall = max(tall, EMPTY_BIN_PIXELS)
        parts.append(
            f"<rect x='{x0 + gap / 2:.2f}' y='{height - tall:.2f}' "
            f"width='{max(x1 - x0 - gap, 0.5):.2f}' height='{tall:.2f}' "
            f"fill='currentColor' fill-opacity='{BAR_OPACITY if count else 0.18:.2f}'/>")
    return "".join(parts)


def bins_outside(counts: list, row, axis=None) -> tuple:
    """How much histogram mass falls OUTSIDE the drawn axis, as `(below, above)`.

    🚨 A237 (cfdb-main-R-3040). NARROWING THE AXIS DROPS BARS, AND THE DROP MUST BE VISIBLE.
    A235's own finding one level over: a mark that is present, correct and off the canvas is
    invisible in the DOM and wrong on the screen. Here the bar is not even drawn, so nothing but
    an explicit count can say it existed.

    📊 MEASURED on 2026 week 3, narrowing to the whisker span costs **0.0% of `winning_points`,
    1.3% of `losing_points` and 4.0% of `total`** — small, which is the argument FOR the trade
    and not a reason to leave it unsaid.
    """
    span = axis_span(row, axis)
    if not counts or span is None:
        return (0, 0)
    axis_lo, axis_hi = span
    bin_lo, bin_hi = float(row["bin_min"]), float(row["bin_max"])
    if bin_hi <= bin_lo:
        return (0, 0)
    incr = (bin_hi - bin_lo) / len(counts)
    below = above = 0
    for index, count in enumerate(counts):
        left, right = bin_lo + index * incr, bin_lo + (index + 1) * incr
        if right <= axis_lo:
            below += count
        elif left >= axis_hi:
            above += count
    return (below, above)


def _bins_of(row) -> Optional[tuple]:
    """The row's own bin range, which is what the published `bin_counts` are spread across.

    ⚠️ DISTINCT FROM `axis_span`, AND A237 EXISTS IN THE GAP BETWEEN THEM. Until this round the
    two were always equal and neither needed a name; narrowing the axis separates *what the bars
    describe* from *what the chart draws*, and every bar has to be placed against both.
    """
    try:
        lo, hi = float(row["bin_min"]), float(row["bin_max"])
    except (KeyError, TypeError, ValueError):
        return None
    return None if hi <= lo else (lo, hi)


def _median_tick(row, width: float, height: float, axis=None) -> str:
    x = _value_to_x(row.get("p50"), row, width, axis)
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
    # 🚨 A150. ONE STATEMENT PER LINE — MARC, v17: *"I like the new hover tooltip, but can you
    # include a `<br>` between each statement"*, with his own five-line sketch beside it.
    #
    # ⚠️ `<br>` IS THE INTENT AND WOULD BE A DEFECT AS AN IMPLEMENTATION. Every consumer of this
    # string is a NATIVE tooltip — three `title='…'` attributes in this module and an SVG
    # `<title>` element in `matchup.py` — and native tooltips render PLAIN TEXT. A literal `<br>`
    # would reach the reader as the four characters `<br>`.
    #
    # ✅ SO THE SEPARATOR IS A NEWLINE AND THE ESCAPING IS THE CALLER'S. This function returns
    # plain text, which is what it has always returned and what makes it testable; `_attr()`
    # turns the newline into `&#10;` for the three attribute call sites. **An SVG `<title>` is
    # ELEMENT content and needs no such thing — a raw newline is already a line break there**,
    # which is the note `matchup.py`'s `_circle_title` needs when B126 makes the same change.
    return "\n".join(bits)


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
    return (f"<span class='cfdb-dist' title='{_attr(describe(row))}'>"
            f"<span class='cfdb-dist-label'>{label}</span>{svg}"
            f"<span class='cfdb-dist-median'>{median_text}</span></span>")


# ── box() ───────────────────────────────────────────────────────────────────────────────────
#
# Marc, 2026-09-14: "For every measure I'd like a horizontal box-whisker plot under the measure
# value. Span the full width of the cell. label upper/lower boundaries... annotate .25, .75.
# Bold line for .50. Blue line with label for Metric Value. Make it easy to configure. I want to
# set labels, tick mark strategy, etc"

# THE VALUE MARKER'S COLOUR, and it is only half of the marker — see `_value_marker`.
VALUE_COLOR = "#2f6fdb"

# 🚨 A239 (cfdb-main-R-3234). THE IQR'S OWN COLOUR — Marc, v19:
# > *"Color p25 and p75 values and labels a dark orange, like burnt sienna. Fill the IQR range
# > with the same orange, or fill with a lighter orange and outline with the dark orange. That
# > will help end-user understand the relationship."*
#
# ⚠️ **THE REASON IS THE REQUIREMENT: a reader should see that the two numbers ARE the box.** So
# the same token paints the p25/p75 text and the box, and nothing else on the chart uses it.
#
# 🚨 IT IS A `var()`, NOT A LITERAL, AND THAT INVERTS COWORK'S INSTRUCTION FOR A MEASURED REASON.
# The prompt asked for the hex here with `theme.py` referencing it. **`theme.py`'s `CSS` is a
# plain string, not an f-string** — interpolating a Python value into it would mean escaping
# every brace in the entire stylesheet. So the literal lives where every other colour token on
# this site already lives (`--cfdb-link`, `--cfdb-u1`, `--cfdb-u2` are all `light-dark()` pairs
# in `theme.py`) and this references it. **One definition either way; this is the direction that
# does not rewrite the stylesheet.**
#
# 📊 AND IT HAD TO BE A PAIR, WHICH THE PROMPT SUSPECTED AND THIS ROUND MEASURED. Marc's
# `#8A3324` scores **8.14:1 on the light canvas and 2.32:1 on the dark one** — the latter is
# below even the 3:1 non-text floor, so a single literal is unreadable in a scheme this site
# ships. The dark-mode variant is measured beside it in `theme.py`.
IQR_COLOR = "var(--cfdb-iqr)"

# 🚨 A244 (cfdb-main-R-3351). THE FAINTEST THING IN THE CHART, AND A TOKEN PAIR BECAUSE A239
# SHIPPED A SINGLE HEX AND IT FAILED ONE MODE (8.14:1 light, 2.32:1 dark). A gridline must read
# as ground rather than as a whisker, a tick or a box edge, so it is defined against the tile
# background in `theme.py` and measured in BOTH modes rather than eyeballed.
GRID_COLOR = "var(--cfdb-grid)"

# TICK STRATEGIES, offered rather than invented. Marc asked to "set tick mark strategy"; these
# are the three the published row can actually support, and `percentiles` is the default because
# it is the only one whose ticks are values the row already carries — the other two derive
# positions the data never named.
TICK_PERCENTILES = "percentiles"   # p25, p50, p75 — the box's own edges
# TICK_BOUNDS draws the whisker ends only — what Marc called "upper/lower boundaries".
TICK_BOUNDS = "bounds"
TICK_NONE = "none"
# 🚨 A150. MIN · MAX · p25 · p75 — MARC, v17: *"label MIN, Max, 25pctl, 75pctl where there is
# room"*, and, when Cowork asked what the whisker ends should then do: *"MIN and MAX should be
# labeled on the axis, the whisker endpoints don't need to be labeled."*
#
# 🚨 HE IS SWAPPING TWO LABELS, NOT ADDING TWO. `TICK_PERCENTILES` prints FIVE — `lo` and `hi`,
# which are the WHISKER ends, then p50, p25, p75. This prints FOUR and neither whisker end is
# among them. **The median is not in his list either**; it stays in the tooltip, and the bold
# rule already draws it on the chart without a number.
#
# ⚠️ A FOURTH STRATEGY RATHER THAN A REDEFINITION, because `TICK_PERCENTILES` is the default that
# every other caller and 130 tests read. Marc asked for strategies in v06 — *"I want to set
# labels, tick mark strategy, etc"* — and this is what those constants are for.
#
# 🚨 IT IMPLIES THE WIDER FRAME, AND THAT IS A CORRECTNESS RULE RATHER THAN A CONVENIENCE. A label
# is a mark, and this module's existing law — A142's — is that a mark at the extreme has to be
# inside the viewBox: "clamping an outlier to the boundary tells the reader it is AT the extreme
# when it is BEYOND it." **A MIN label placed against a frame that stops at the whisker would sit
# on top of the whisker end and say the minimum is there.** So asking for these ticks asks for
# the frame that can hold them honestly.
TICK_EXTREMES = "extremes"

# 🚨 A237 (cfdb-main-R-3041). THE FIFTH STRATEGY, AND IT IS THE ONLY ONE THAT PRINTS NOTHING.
#
# > **MARC, 2026-09-25:** *"Add an x-axis below the histogram with major tickmarks at increments
# > of 5 (counting from a baseline of 0, so 5, 10, 15, etc for the scores that are in scope).
# > Don't need to include the values for the tickmarks, just the ticks, which should take up
# > minimal vertical space."*
#
# ⚠️ IT IS A FIFTH STRATEGY RATHER THAN A FLAG ON TICK_BOUNDS, AND THE REASON IS THAT IT ANSWERS
# A DIFFERENT QUESTION. The other four all ask *which of this row's statistics deserve a label* —
# they emit VALUES, chosen from the row, and compete for horizontal room through `_LabelBands`.
# This one emits a RULER: marks at every multiple of a step, carrying no text, competing with
# nothing. Folding it into `_axis_ticks` would mean that function returned values that are
# sometimes labelled and sometimes not, which is the kind of overload that reads fine and breaks
# the next caller.
#
# ⚠️ "COUNTING FROM A BASELINE OF 0" IS A MODULUS, NOT A START POINT — and it matters precisely
# because A237 also narrows the axis. The first tick is the lowest multiple of the step INSIDE
# the axis, which is 15 on an axis starting at 14, not 14. Ticks on a ruler have to mean the same
# value on every chart or they are decoration.
TICK_STEP = "step"

# The tick band's own height. Marc asked for "minimal vertical space", and this is what that
# costs: a 3px mark plus 2px of clearance, against `LABEL_BAND`'s 15 for a row of digits.
TICK_BAND = 5
TICK_MARK = 3

# The overflow arrow's depth, in px. It points OUT of the plot and sits entirely INSIDE the
# viewBox — see the draw site for why that distinction cost a render.
OVERFLOW_MARK = 5.0

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
#     _RECT_HALF_RATIO   7   / 26   the box rect's half-thickness
#     _SERIF_HALF_RATIO  7.5 / 26   the whisker serif's half-height
#
# ── A155: THE SERIF GETS 50% TALLER, AND IT OUTRANKS THE BOX NOW ─────────────────────────────
#
# > **MARC, v19, verbatim:** *"increase the size of the whisker outer boundary lines by 50%"*
#
# ✅ THE OUTER BOUNDARY LINES ARE THE SERIFS — the short verticals capping each whisker. They are
# the only thing on this chart that answers to that description: the MIN/MAX reference lines A154
# added are already the full band, so *"increase the size"* cannot mean those, and the whisker
# RULE is horizontal — it has no size to increase in the direction this changes.
#
# ⚠️ *"SIZE"* IS READ AS LENGTH RATHER THAN STROKE WIDTH, and v18 is the reason rather than taste:
# it asked the WEIGHT question one round earlier under its own word — *"increase the darknes of
# Whisker structure/outline by 25%"* — and got `WHISKER_OPACITY`. A round that spent "darkness" on
# weight is unlikely to spend "size" on it too. 📷 The stroke-width reading (`1` → `1.5`) is
# rendered beside this one in `claude_work/renders/A155_serif_length_vs_stroke_width.png`, so the
# other answer costs one word rather than another round.
#
# 🚨 AND IT INVERTS THE TWO MARKS' HIERARCHY, WHICH MARC HAS NOT SEEN AND SHOULD:
#
#     before   serif 5/26   SHORTER than the rect 7/26   — the box is the taller mark
#     after    serif 7.5/26 TALLER   than the rect 7/26   — the whisker ends are
#
# ⚠️ That is a change to the picture's pecking order, not a size tweak. It may be exactly what he
# wants — the ends are what he has been trying to see since v17 — but it is the kind of thing a
# render decides and a comment cannot: `claude_work/renders/A155_the_serif_outranks_the_box.png`.
#
# 🚨 THIS ONE MOVES BYTES ON EVERY CHART AND THAT IS INTENDED. The ratios exist so the furniture
# scales with `height`, and until now `5.0 / 26 * 26` returned exactly 5.0 so every emitted string
# was unchanged. Marc asked for this globally, exactly as A154's darkening was asked for, so it is
# not a new capability and there is no flag. ✅ THE BYTE-IDENTITY PROOF THEREFORE INVERTS: the test
# is no longer *nothing moved* but *the ONLY thing that moved is the serif's two y coordinates* —
# see `test_the_serif_is_the_only_thing_that_moved`.
#
# At `height=BOX_HEIGHT` these return exactly 7.0 and 7.5.
_RECT_HALF_RATIO = 7.0 / BOX_HEIGHT
_SERIF_HALF_RATIO = 7.5 / BOX_HEIGHT

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

# 🚨 A154 — MARC, v18: *"Increase the font on the value being plotted for the team"*. The axis
# labels stay at 9; the team's own figure goes to 11.
#
# ⚠️ AND IT COSTS WIDTH FROM THE BUDGET THE FOUR AXIS LABELS COMPETE FOR, which is why
# `_text_width` is scaled by the ratio when the value is measured for collision. A label that
# reserves a 9px-wide box and paints an 11px-wide one overlaps its neighbour silently — the same
# class as B108's `scrollWidth` reading the slot rather than the glyphs.
VALUE_LABEL_FONT = 11
_VALUE_LABEL_SCALE = VALUE_LABEL_FONT / 9.0

# ── A154: THE STRUCTURE'S WEIGHTS, AND MARC'S TWO CANDIDATES FOR THE EXTREME LINE ────────────
#
# > **MARC, v18:** *"Increase the darknes of Whisker structure/outline by 25%"* and *"Min/Max
# > should have tickmarks reference lines that are 25% below what the whisker structure started in
# > this round, or 50% lower than whisker structure started."*
#
# 🚨 THE STRUCTURE HAS TWO WEIGHTS, NOT ONE, AND THE PROMPT SAID ONE. Read at `4e59ee3`: the
# whisker line and its serifs draw at **`opacity='.55'`**; the box rect's outline draws at
# **`stroke-opacity='.5'`** — a different value AND a different attribute. Cowork's spec note said
# *"the box and whisker structure draws at stroke-opacity='.5'"*, which is true of the rect alone.
# ✅ SO EACH ELEMENT DARKENS 25% FROM ITS OWN BASELINE, which is what his sentence asks for when
# the thing being darkened is not uniform.
#
# ⚠️ AND THE EXTREME LINE IS MEASURED FROM THE WHISKER'S START, because that is the noun he used —
# *"what the whisker structure started in this round"* — and the whisker started at .55.
_WHISKER_OPACITY_WAS = 0.55
_BOX_OUTLINE_OPACITY_WAS = 0.5
WHISKER_OPACITY = 0.6875            # .55 + 25%
BOX_OUTLINE_OPACITY = 0.625         # .50 + 25%
# 🚨 BOTH OF HIS CANDIDATES ARE HERE AND NEITHER IS CHOSEN FOR HIM (the R-895 pattern). The
# default is the one he listed FIRST; the pair is rendered in the report for him to pick.
EXTREME_LINE_OPACITY = 0.4125       # .55 − 25%, the default
EXTREME_LINE_OPACITY_LIGHTER = 0.275   # .55 − 50%, the alternative

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


# ── A235 (cfdb-main-R-3029). TWO THINGS `box()` OWNED PRIVATELY AND `panel()` NOW NEEDS ──────
#
# 🚨 MARC ASKED FOR ONE PICTURE THAT NO ENTRY POINT DREW. His v18 wants the histogram and the
# box-whisker *"x-axis aligned"* AND *"an x-axis with labels"*, and measured at `a7e1f78`:
#
#     panel()   histogram + box in ONE SVG on one scale  ✅   axis labels: NONE
#     box()     axis labels, four tick strategies        ✅   reads no bin column at all
#
# ⚠️ SO THE GAP IS NOT A MISSING FUNCTION, IT IS A LABEL BAND `panel()` HAS NEVER HAD. The two
# helpers below are lifted OUT of `box()`'s body unchanged rather than reimplemented beside it,
# because a second copy of the collision rule is a copy that drifts — and the drift would be
# invisible: two charts whose labels disagree about which one fits still both look fine.
#
# ✅ `tests/test_distribution_axis_labels.py` PINS `box()`'s OUTPUT BYTE-FOR-BYTE ACROSS EVERY
# TICK STRATEGY, so the extraction is provably inert for the 130-odd tests and every live call
# site that already read it.
class _LabelBands:
    """First-come-first-served label placement, one contest per baseline.

    The three rules are `box()`'s and are unchanged: the caller's own figure is placed first and
    wins, a label that would collide is DROPPED rather than shifted (a shifted label points at
    the wrong place on the axis, which is worse than one fewer label), and every label is clamped
    inside the frame so the viewBox cannot clip it.
    """

    def __init__(self, width: float, pad: float):
        self.width, self.pad = width, pad
        self.bands: dict = {}

    def place(self, band: str, x: float, text: str, color: Optional[str] = None,
              scale: float = 1.0) -> None:
        # Half the label's MEASURED width each side is the exclusion zone — see _ADVANCE_9PX
        # for why this is summed per character rather than averaged over the length.
        half = _text_width(text) * scale / 2.0
        x = min(max(x, self.pad + half - 8), self.width - self.pad - half + 8)
        placed = self.bands.setdefault(band, [])
        for other_x, other_half, _, _ in placed:
            # Touching boxes plus a constant of clear space. No multiplier: see LABEL_GAP.
            if abs(x - other_x) < half + other_half + LABEL_GAP:
                return
        placed.append((x, half, text, color))

    def get(self, band: str) -> list:
        return self.bands.get(band, [])


def _axis_ticks(row, ticks: str) -> list:
    """The values a tick strategy labels, IN THE ORDER THAT DECIDES WHICH SURVIVE.

    🚨 THE ORDER IS LOAD-BEARING RATHER THAN TIDY, because `_LabelBands.place` is
    first-come-first-served and drops whatever will not fit. Marc, v17: *"label MIN, Max, 25pctl,
    75pctl where there is room"* — so when the four cannot all fit, the two he named first
    survive, which are also the two the chart has never shown before.

    ⚠️ THE WHISKER ENDS ARE NOT LABELLED UNDER `TICK_EXTREMES` — Marc, v17: *"the whisker
    endpoints don't need to be labeled"*. Every other strategy prints them exactly as before.

    ⚠️ A MISSING VALUE IS SKIPPED, NEVER DRAWN AT A SUBSTITUTE POSITION (R-084). `min_value` and
    `max_value` are published by all four distribution siblings, but this module does not require
    them — a hand-built row without them labels what it has.
    """
    def num(key):
        raw = row.get(key)
        return None if raw is None or pd.isna(raw) else float(raw)

    if ticks == TICK_NONE:
        return []
    raw_lo, raw_hi = _whisker_pair(row)
    lo = None if raw_lo is None or pd.isna(raw_lo) else float(raw_lo)
    hi = None if raw_hi is None or pd.isna(raw_hi) else float(raw_hi)
    if ticks == TICK_EXTREMES:
        wanted = (num("min_value"), num("max_value"), num("p25"), num("p75"))
    elif ticks == TICK_PERCENTILES:
        wanted = (lo, hi, num("p50"), num("p25"), num("p75"))
    else:
        wanted = (lo, hi)
    return [v for v in wanted if v is not None]


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


def _attr(text: str) -> str:
    """Text for an HTML ATTRIBUTE, which is a different job from `_esc`'s element content.

    🚨 THE NEWLINE IS THE WHOLE REASON THIS EXISTS (A150). `describe()` now separates its
    statements with `\n` and the three call sites interpolate it straight into `title='…'`. A raw
    newline inside an attribute is fragile — it survives a browser but not necessarily a
    sanitiser between here and one — so it is emitted as the numeric reference `&#10;`, which is
    a line break in every native tooltip and is not markup anybody can mangle.

    ⚠️ `_esc`'s docstring says the attributes "are NOT routed through here and that is deliberate:
    changing them would move bytes on every chart the site already draws". ✅ **That reasoning was
    right and its premise is gone** — this round moves those bytes on purpose, so escaping them
    correctly costs nothing extra and closes the gap that comment was tolerating.
    📊 On every published row, escaping changes NOTHING but the newline: `describe()` composes
    from numbers, fixed words and a date, and carries no `&`, `<`, `>` or `'` — measured, not
    assumed.
    """
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("'", "&#39;").replace("\n", "&#10;"))


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


# 🚨 A243 (cfdb-main-R-3322). THE ORDERED REGISTRY AND THE DEFAULT ARE NOW TWO THINGS.
#
# > **MARC, v20:** *"Add p05 and p95 to the stats shown to the right of the KPI"*
#
# ⚠️ THEY WERE ONE LIST, AND IT DID TWO JOBS: it fixed the ORDER any subset renders in, and it was
# also what `keys=True` drew. Adding p05/p95 to a single list would have put them on every full
# panel as well — **Marc asked for them beside the KPI, not everywhere.**
#
# 📊 MEASURED BEFORE SPLITTING, because the risk turned out to be smaller than it looks: **no
# live caller passes `keys=True` at all.** `site/` contains exactly two stats consumers —
# `today._kpi_chart` (`stats=False`) and `today._kpi_stats` (explicit keys) — so `keys=True` is
# exercised only by tests today. ✅ **The split is still right**: it stops the next full-panel
# caller inheriting five rows because the KPI wanted them.
PANEL_STATS = (("n", "n"), ("min", "min_value"), ("p05", "p05"), ("p25", "p25"),
               ("median", "p50"), ("p75", "p75"), ("p95", "p95"), ("max", "max_value"))

# What `keys=True` renders — the six a full panel has always shown, unchanged.
DEFAULT_STATS = (("n", "n"), ("min", "min_value"), ("p25", "p25"), ("median", "p50"),
                 ("p75", "p75"), ("max", "max_value"))


def stats_table(row, keys=True) -> str:
    """The statistics table, label-left value-right monospace. ONE implementation, two callers.

    🚨 A237 (cfdb-main-R-3042). `panel()` DRAWS THIS BESIDE THE CHART; MARC WANTS IT BESIDE THE
    KPI VALUE.
    > **MARC, 2026-09-25:** *"How about a tight table to the right KPI value that shows p25, p50,
    > p75."*

    ⚠️ THE TILE CANNOT REACH INSIDE `panel()`'s MARKUP TO MOVE IT — the block is nested two divs
    deep inside the chart, and the value it wants to sit beside is rendered before the chart even
    starts. **So the table is factored out rather than reimplemented**, which is exactly what A235
    did with `_LabelBands` and for the same reason: a second copy of a renderer is a copy that
    drifts, and the drift here would be two tables of the same numbers formatted differently on
    one screen.

    `keys` is `True` for `DEFAULT_STATS`, `False` for none, or a sequence of COLUMN names drawn
    from `PANEL_STATS`.
    ⚠️ The ORDER is `PANEL_STATS`'s, never the caller's — so two callers asking for the same rows
    cannot get them in different orders. ⚠️ And `True` renders `DEFAULT_STATS`, NOT the whole
    registry: the registry is what MAY be asked for, the default is what a full panel shows (A243).
    """
    wanted = (DEFAULT_STATS if keys is True else
              () if keys is False or keys is None else
              tuple(pair for pair in PANEL_STATS if pair[1] in tuple(keys)))
    if not wanted:
        return ""
    # 🚨 A239: THE TWO QUARTILE ROWS ARE MARKED, so one CSS rule colours the label AND the value
    # in the same orange as the box they describe — which is Marc's stated reason rather than a
    # decoration: *"a reader should see that the two numbers ARE the box."*
    # ⚠️ `median` IS NOT MARKED. He coloured two of the three, and the third is the bold rule on
    # the chart rather than an edge of the box.
    cells = []
    for name, key in wanted:
        value = row.get(key)
        shown = "\u2013" if value is None or pd.isna(value) else (
            f"{int(value)}" if key == "n" else fmt.number(float(value), dp=1))
        cls = "cfdb-dist-stat cfdb-iqr" if key in ("p25", "p75") else "cfdb-dist-stat"
        cells.append(f"<div class='{cls}'><span>{name}</span><b>{shown}</b></div>")
    return f"<div class='cfdb-dist-stats'>{''.join(cells)}</div>"


def panel(row, label: str = "", width: int = 420, *,
          height: Optional[int] = None, ticks: str = TICK_NONE,
          head: bool = True, stats=True, dp=_UNSET, metric: str = "",
          axis=None, tick_step: Optional[float] = None,
          tick_label_step: Optional[float] = None,
          histogram: bool = True, box_height: Optional[int] = None,
          gridlines=()) -> str:
    """The same picture with room to read it: the histogram, the box-and-whisker beneath it on
    a SHARED X-SCALE, and the statistics as a table beside it.

    The stats block is a table, not a caption — label left, value right, monospace — which is
    what `plot_distribution` does and is the part that makes the numbers scannable.

    🚨 A235 MOVED THIS FUNCTION DOWN THE FILE AND CHANGED NOTHING ABOUT ITS DEFAULT OUTPUT. It
    sits below `_LabelBands`, `_axis_ticks` and `_whisker_pair` because it now uses all three, and
    Python resolves a default argument at `def` time — `ticks: str = TICK_NONE` cannot be written
    above the constant it names. **It had ZERO call sites in `site/` when it moved**, so the move
    could not break a caller; `tests/test_distribution_axis_labels.py` pins the default render.

    ⚠️ FIVE KEYWORD-ONLY PARAMETERS, NOT A FOURTH DRAWING FUNCTION. Marc's v18 asks the KPI row
    for a chart this module could ALMOST already draw: the aligned pair is here, the axis labels
    were in `box()`, and nothing had both. The KPI tile also supplies its own label, figure and
    denominator, so the panel's head and stats block would print each of them twice.

        height   the histogram band. `PANEL_HEIGHT` when unasked; the box and the label band are
                 sized from it, so one number moves the whole chart
        ticks    TICK_NONE (default, and the byte-identical one) | TICK_BOUNDS | TICK_PERCENTILES
                 | TICK_EXTREMES — Marc's *"x-axis with labels"*, drawn in a band below the box
        head     the label and the bin subtitle. OFF for a caller that already names the measure
        stats    True for the full n/min/p25/median/p75/max table beside the chart, False for
                 none, or a SEQUENCE OF KEYS for a subset — `("p25", "p50", "p75")` is Marc's
                 *"tight table to the right KPI value that shows p25, p50, p75"* (A237)
        dp       decimals for the tick labels; defaults via `fmt.precision_for(metric)`
        metric   the metric's COLUMN NAME, used only to choose `dp` — `box()`'s rule, one place
        axis     `(lo, hi)` to DRAW instead of the bin range — A237. Narrows, and the mass it
                 drops is marked at the edge rather than clipped away silently
        tick_step
                 with `ticks=TICK_STEP`, the interval between tick marks. Marks land on
                 multiples of it, so the first is the lowest multiple inside the axis
        histogram
                 draw the bars at all. OFF is Marc's v20 — *"Remove the histograms"* — and it
                 leaves the box, the axis and the tick ruler exactly where they were (A243)
        box_height
                 the box band in pixels, EXPLICIT. Defaults to the historic `max(hist//4, 12)`,
                 which is meaningless once there is no histogram to take a quarter of
        tick_label_step
                 with `ticks=TICK_STEP`, ALSO print a value at every multiple of this — A239,
                 Marc's *"Label x-axis on the even values (10, 20, 30, etc)"*. The marks stay at
                 `tick_step`; only some of them get a number. Costs `LABEL_BAND` instead of
                 `TICK_BAND`, which is the vertical price and is measured in A239's report

    🚨 AND THE SVG'S WIDTH BEHAVIOUR IS DECIDED BY WHETHER THERE IS TEXT IN IT, WHICH IS A
    CORRECTNESS RULE RATHER THAN A PREFERENCE. With no ticks the SVG keeps `width='100%'` and
    `preserveAspectRatio='none'`, so it fills its container and the bars simply get wider — the
    behaviour every existing render has. **`preserveAspectRatio='none'` scales TEXT
    non-uniformly**, so the moment a tick label exists that stretch would render the digits
    squashed or splayed by whatever ratio the container happened to have. A labelled panel is
    therefore a FIXED-WIDTH SVG with `max-width:100%`, which is exactly what `box()` does and for
    the same reason.
    """
    if row is None:
        return ("<div class='cfdb-dist-panel cfdb-dist-empty'>"
                "cfdb holds no distribution for this week yet.</div>")

    counts = parse_bin_counts(row.get("bin_counts"))
    # 🚨 A243 (cfdb-main-R-3320). > **MARC, v20:** *"Remove the histograms. Increase the vertical
    # size of the box-whisker chart (not the axis and tickmarks) by 50%."*
    # ⚠️ WITH NO HISTOGRAM THERE IS NO BAND TO TAKE A QUARTER OF, so the box height stops being
    # derived and becomes the caller's. 📊 Measured from the rendered SVG before changing it: the
    # box band was **12px** (`max(28 // 4, 12)`) inside a **140 x 55** viewBox.
    hist_height = 0 if not histogram else (PANEL_HEIGHT if height is None else int(height))
    # ⚠️ THE BOX KEEPS ITS PROPORTION OF THE BAND, WHICH IS A145's RULE ONE LEVEL OVER: a box
    # plot has no y quantity, so its THICKNESS is decoration and scales, while nothing that
    # carries a number moves. The floor stops the box collapsing to a rule at a short height.
    box_band = int(box_height) if box_height is not None else max(hist_height // 4, 12)

    # THE BOX SITS ON THE HISTOGRAM'S OWN SCALE. Drawn in one SVG rather than two stacked, so
    # the axes cannot drift apart — which is the same reason the thumbnail and this share
    # `_bars`. 🚨 IT IS ALSO WHAT MARC ASKED FOR IN v18 — *"Histogram and Box-Whisker x-axis have
    # to be aligned"* — and it was already true here; what was missing was the labels.
    box = []
    # ── A244 (cfdb-main-R-3351): THE MAJOR GRIDLINES, AND THEY ARE EMITTED FIRST ─────────────
    #
    # > **MARC, v21:** *"Can you add major gridlines at 0, 20, 40, 60, and 80? They can be muted
    # > down a bit, but it will help comparisons across Win, Loss, and Total KPI's."*
    #
    # 🚨 FIRST INTO `box`, WHICH IS THE WHOLE MECHANISM. SVG has no z-index — it paints in
    # document order — so a gridline appended anywhere else would sit ON TOP of the box, the
    # median rule and the overflow mark. Being first is what makes it a background.
    #
    # ⚠️ THE VALUES ARE THE CALLER'S, NOT DERIVED FROM THE TICK STEP. Marc named five specific
    # values and they are not every second tick label: the ruler labels 0..80 by 10, and the
    # gridlines are the 20s. Deriving them would couple two things he asked for separately.
    #
    # ⚠️ A GRIDLINE OUTSIDE THE FRAME IS DROPPED, NOT CLAMPED. `_value_to_x` returns None there,
    # and a gridline clamped to the edge would draw a line labelled 80 somewhere that is not 80
    # — A142's law, the same one the overflow mark exists to respect.
    for value in (gridlines or ()):
        gx = _value_to_x(float(value), row, width, axis)
        if gx is None:
            continue
        box.append(f"<line x1='{gx:.1f}' y1='{hist_height:.1f}' x2='{gx:.1f}' "
                   f"y2='{hist_height + box_band:.1f}' stroke='{GRID_COLOR}' "
                   f"stroke-width='1'/>")
    # 🚨 A243: CLAMPED, NOT DROPPED. On a fixed axis a whisker beyond the frame would otherwise
    # simply not be drawn — see `clamped_to_axis` for the two failure modes this replaces. Every
    # clamp is recorded so the edge can be MARKED; a silent clamp is a lie about where the value is.
    clamped = set()

    def at(value):
        x, side = clamped_to_axis(value, row, width, axis)
        if side:
            clamped.add(side)
        return x

    q1 = at(row.get("p25"))
    q3 = at(row.get("p75"))
    raw_lo, raw_hi = _whisker_pair(row)
    lo = at(raw_lo)
    hi = at(raw_hi)
    mid = hist_height + box_band / 2
    if lo is not None and hi is not None:
        box.append(f"<line x1='{lo:.1f}' y1='{mid:.1f}' x2='{hi:.1f}' y2='{mid:.1f}' "
                   f"stroke='currentColor' stroke-opacity='.6'/>")
        for end in (lo, hi):
            box.append(f"<line x1='{end:.1f}' y1='{mid - 4:.1f}' x2='{end:.1f}' "
                       f"y2='{mid + 4:.1f}' stroke='currentColor' stroke-opacity='.6'/>")
    if q1 is not None and q3 is not None:
        # 🚨 A239: MARC'S SECOND OPTION — *"fill with a lighter orange and outline with the dark
        # orange"* — achieved with ONE token rather than two, so the fill and the outline cannot
        # drift into different hues. The opacity does the lightening.
        box.append(f"<rect x='{q1:.1f}' y='{hist_height + 2:.1f}' "
                   f"width='{max(q3 - q1, 1):.1f}' height='{box_band - 4}' "
                   f"fill='{IQR_COLOR}' fill-opacity='.22' stroke='{IQR_COLOR}' "
                   f"stroke-opacity='.85'/>")
    median_x = at(row.get("p50"))
    if median_x is not None:
        box.append(f"<line x1='{median_x:.1f}' y1='{hist_height + 2:.1f}' "
                   f"x2='{median_x:.1f}' y2='{hist_height + box_band - 2:.1f}' "
                   f"stroke='currentColor' stroke-width='2'/>")

    # ── THE AXIS LABEL BAND ──────────────────────────────────────────────────────────────────
    #
    # ⚠️ THE TICKS ARE PLACED ON THE HISTOGRAM'S SCALE, NOT ON `box()`'s. `box()` frames on the
    # whiskers and pads; this frames on `bin_min`..`bin_max`, because that is the axis the bars
    # are drawn against and the whole point of the shared scale. `_value_to_x` returns None for a
    # value outside the bins, which is the honest answer — `below_min_count`/`above_max_count`
    # already tell the reader the tail is off the axis, and a label clamped to the edge would say
    # the extreme is AT the boundary when it is beyond it (A142's rule).
    if dp is _UNSET:
        dp = fmt.precision_for(metric) if metric else 1

    # ── A237: THE OVERFLOW MARKS, DRAWN BEFORE THE AXIS SO THEY SIT UNDER IT ────────────────
    #
    # 🚨 A NARROWED AXIS DROPS BARS AND SOMETHING HAS TO SAY SO. A142's law is that a mark at the
    # boundary must not claim to BE at the boundary, so this is deliberately NOT a bar squeezed
    # against the edge: it is a solid triangle pointing OUT of the plot, which says *there is
    # more this way* and names no value at all. The count rides in the chart's own `<title>`.
    # 🚨 IT POINTS OUT AND IT SITS IN. The first draft put the tip at `width + 4.5` on a viewBox
    # `0 0 {width} …` — **present in the DOM, correct in every attribute, and clipped off the
    # canvas.** A237's own crop caught it, which is A235's clipped `0` repeated by the round that
    # had just written the test for it: `polygons: 1` and nothing on screen. The apex now lands ON
    # the edge and the base is inset, so the mark is entirely inside the frame.
    below_out, above_out = bins_outside(counts, row, axis) if histogram else (0, 0)
    # ⚠️ A243: THE EDGE IS MARKED FOR EITHER REASON — histogram mass beyond the frame (A237's
    # case) OR a box/whisker mark that had to be clamped to it (this round's). With the histogram
    # gone the first can no longer happen, and the second is the only thing that can say a value
    # fell off the end. 🚨 That is why `bins_outside` is not simply deleted with the bars.
    for count, side, edge_x, direction in ((below_out, "lo", 0.0, -1),
                                           (above_out, "hi", float(width), 1)):
        if not count and side not in clamped:
            continue
        base_x = edge_x - direction * OVERFLOW_MARK
        base_y = hist_height - 3.5
        box.append(
            f"<polygon points='{edge_x:.1f},{base_y:.1f} {base_x:.1f},{base_y - 3.5:.1f} "
            f"{base_x:.1f},{base_y + 3.5:.1f}' fill='currentColor' fill-opacity='.55'>"
            f"<title>{_beyond_note(count, side in clamped)}</title></polygon>")

    # ── THE TICK RULER — Marc's "just the ticks", minimal vertical space ────────────────────
    #
    # ⚠️ MULTIPLES OF THE STEP, NOT STEPS FROM THE LEFT EDGE. See TICK_STEP: on an axis starting
    # at 14 the first mark is 15. A ruler whose marks mean a different value on each chart is
    # decoration, and two tiles side by side is exactly where that would show.
    tick_band = 0
    if ticks == TICK_STEP:
        # 🚨 A239: LABELLING SOME OF THE MARKS COSTS THE FULL LABEL BAND, and A237 bought that
        # room by halving the bars. Marc, v19: *"Label x-axis on the even values (10, 20, 30,
        # etc)"* — read as **keep the marks every 5 and put a number on the multiples of 10**,
        # which is the reading that keeps A237's ruler and adds what he asked for. The two other
        # readings (marks only at 10s, or a number on every mark) are named in the report.
        label_step = float(tick_label_step or 0)
        tick_band = LABEL_BAND if label_step > 0 else TICK_BAND
        span = axis_span(row, axis)
        step = float(tick_step or 0)
        if span and step > 0:
            axis_lo, axis_hi = span
            first = math.ceil(axis_lo / step) * step
            baseline = hist_height + box_band
            # ⚠️ ONE PLACEMENT RULE, NOT TWO. `_LabelBands` was extracted by A235 precisely so a
            # second caller could not invent its own contest — it clamps inside the frame and
            # DROPS a label that would collide rather than shifting it to a wrong value.
            # `pad=8.0` cancels its overhang for a panel, exactly as the label band below does.
            ruler = _LabelBands(width, 8.0) if label_step > 0 else None
            # 🚨 A239 (cfdb-main-R-3236). AN AXIS TICK IS A POSITION, NOT A MEASUREMENT, and a
            # multiple of a whole step is always whole — so it prints whole. 📊 The raster is
            # what raised it: the O/U tile read `40.0  50.0  60.0` beside two tiles reading
            # `0  10  20`, because `fmt.precision_for("total")` is 1 and the ruler had inherited
            # the METRIC's precision. That 1 decimal is right for the FIGURE — a closing total
            # really is 49.5 — and it is false precision on a ruler whose marks land on 10s.
            # ⚠️ `dp` is untouched for every other strategy: `TICK_EXTREMES` labels `min_value`
            # and `p25`, which are measurements and can genuinely carry a decimal.
            tick_dp = 0 if float(label_step).is_integer() else dp
            # ⚠️ A GUARD ON THE COUNT, NOT ON THE LOOP: a tiny step against a wide axis would
            # emit thousands of marks into the DOM. 200 is far more than any readable ruler and
            # far less than a runaway.
            n = 0
            value = first
            while value <= axis_hi + 1e-9 and n < 200:
                x = _value_to_x(value, row, width, axis)
                if x is not None:
                    box.append(
                        f"<line x1='{x:.1f}' y1='{baseline + 1:.1f}' x2='{x:.1f}' "
                        f"y2='{baseline + 1 + TICK_MARK:.1f}' stroke='currentColor' "
                        f"stroke-opacity='.45'/>")
                    if ruler is not None and abs(value / label_step
                                                 - round(value / label_step)) < 1e-9:
                        ruler.place("below", x, fmt.number(value, dp=tick_dp))
                value += step
                n += 1
            if ruler is not None:
                text_y = baseline + 1 + TICK_MARK + 8
                for lx, _half, text, _color in ruler.get("below"):
                    box.append(
                        f"<text x='{lx:.1f}' y='{text_y:.1f}' text-anchor='middle' "
                        f"font-size='9' fill='currentColor' opacity='.65'>{text}</text>")

    label_band = LABEL_BAND if ticks not in (TICK_NONE, TICK_STEP) else 0
    if label_band:
        # 🚨 `pad=8.0` IS NOT A MARGIN, IT CANCELS `place()`'s OVERHANG — and a raster found it.
        # `_LabelBands.place` clamps to `[pad + half - 8, width - pad - half + 8]`: the ±8 lets a
        # label hang slightly outside the FRAME, which is right for `box()`, where the frame is
        # inset from the viewBox by its own `pad` and there is room to hang into. **A panel's
        # histogram starts at x=0**, so with `pad=0` the same expression clamps a left-edge label
        # to `half - 8` — outside the viewBox, where it is clipped. 📊 MEASURED ON THE LOSING
        # SCORE TILE, whose `min_value` is 0: the crop at 1440 rendered `)` where `0` belonged.
        # ⚠️ AND IT WAS INVISIBLE IN THE DOM — the `<text>` element was present, correct and
        # half off the canvas (R-855's family: the picture caught what reading could not).
        # `pad=8` makes the two constants cancel and the clamp become `[half, width - half]`,
        # which is exactly inside.
        bands = _LabelBands(width, 8.0)
        for edge in _axis_ticks(row, ticks):
            at_x = _value_to_x(edge, row, width, axis)
            if at_x is not None:
                bands.place("below", at_x, fmt.number(edge, dp=dp))
        baseline = hist_height + box_band + 11
        for x, _half, text, _color in bands.get("below"):
            box.append(f"<text x='{x:.1f}' y='{baseline:.1f}' text-anchor='middle' "
                       f"font-size='9' fill='currentColor' opacity='.65'>{text}</text>")

    total_height = hist_height + box_band + label_band + tick_band
    # 🚨 FIXED WIDTH THE MOMENT THERE IS TEXT. See the docstring: `preserveAspectRatio='none'`
    # distorts glyphs, and a squashed numeral on an axis is a legibility defect that is invisible
    # in the DOM — every <text> element present, correct and unreadable (R-855's family).
    # ⚠️ THE ATTRIBUTE ORDER IS LOAD-BEARING FOR THE UNLABELLED CASE AND THAT IS NOT PEDANTRY.
    # A145's rule is that a default may not move a byte of an existing render, and the first
    # draft of this change reordered `preserveAspectRatio` ahead of `height` — semantically
    # identical, textually different, and the identity test caught it. `:g` is not needed here
    # because `total_height` is an int throughout.
    sizing = (f"width='100%' height='{total_height}' preserveAspectRatio='none'"
              if not (label_band or tick_band)
              else f"width='{width}' height='{total_height}' "
                   f"style='display:block;max-width:100%'")
    svg = (f"<svg class='cfdb-dist-svg' viewBox='0 0 {width} {total_height}' "
           f"{sizing} "
           f"aria-hidden='true'>"
           f"{_bars(counts, width, hist_height, _bins_of(row), axis_span(row, axis)) if histogram else ''}"
           # 🚨 A243: THE HISTOGRAM'S MEDIAN TICK GOES WITH THE HISTOGRAM. Measured before the
           # change: the SVG carried TWO median marks — this one on the bar band AND the box's own
           # bold rule. Keeping it with no bars would orphan it above an empty band; keeping both
           # was already a duplication nobody had noticed.
           f"{_median_tick(row, width, hist_height, axis) if histogram else ''}"
           f"{''.join(box)}</svg>")

    # ⚠️ NOT `stats`, WHICH IS THE PARAMETER. The first draft built the table into a local called
    # `stats` and then tested `if stats else ""` — which read the LIST, always truthy, so
    # `stats=False` was silently inert and the KPI tile printed the table it had asked not to.
    # A shadowed parameter fails by doing nothing, which is the hardest kind to see.
    # ⚠️ A237: `stats` IS NO LONGER ONLY A BOOLEAN. True keeps all six, False keeps none, and a
    # sequence of KEYS keeps a subset in `PANEL_STATS`'s order — which is how Marc's *"tight table
    # ... that shows p25, p50, p75"* is three rows of the table that already existed rather than a
    # second table beside it.
    stats_html = stats_table(row, stats)

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

    head_html = (f"<div class='cfdb-dist-head'><b>{label}</b>"
                 f"<span class='cfdb-dist-sub'>{subtitle}{tail_note}</span></div>"
                 if head else "")

    return (f"<div class='cfdb-dist-panel' title='{_attr(describe(row))}'>"
            f"{head_html}"
            f"<div class='cfdb-dist-body'>{svg}"
            f"{stats_html}</div></div>")


def box(row, value=None, width: int = 240, label: str = "",
        ticks: str = TICK_PERCENTILES, show_value: bool = True,
        value_label: Optional[str] = None, dp=_UNSET, metric: str = "",
        value_color: Optional[str] = None,
        value_below=_UNSET, value_below_label: Optional[str] = None,
        value_below_color: Optional[str] = None,
        frame: Optional[tuple] = None, outliers: bool = False,
        frame_extremes: bool = False, extreme_lines: bool = False,
        extreme_line_opacity: float = EXTREME_LINE_OPACITY,
        value_labels_own_row: bool = False,
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
    frame_extremes     widen the scale to `min_value`/`max_value` and draw NOTHING there — A150,
                       Marc's v17: "the boundaries of the chart should extend to the MIN and
                       MAX". OFF BY DEFAULT. `outliers` and `ticks=TICK_EXTREMES` each imply it,
                       because a ring and a label both have to sit inside the viewBox to be
                       truthful; this is the third way to ask, for a caller that wants neither
    value_title        hover text for the value marker — a native SVG `<title>`, measured to
                       survive Streamlit's sanitiser. The words are the caller's (§4.2.1)
    value_below_title  as `value_title`, for the below side
    height             the plot band in pixels, default `BOX_HEIGHT`. The vertical furniture
                       scales with it and NO MEASUREMENT DOES — see the ratios above. A caller
                       overlaying marks inside the band asks for the height those marks need

    ⚠️ THE FOUR BELOW ARE A154's AND WERE LEFT OUT OF THIS LIST — cfdb-main-R-1152, found by B128
    reading it from the call site's side. The body comments explained all four; the list a caller
    actually reads did not mention them, which is the half that matters.

    metric             the metric's COLUMN NAME, used only to choose `dp` when `dp` is not given.
                       ✅ `fmt.precision_for` owns that rule and has since R-555; passing the name
                       asks it rather than restating it at the call site (§4.2.1). Passing NEITHER
                       `dp` nor `metric` keeps the historic literal 1
    extreme_lines      draw `min_value`/`max_value` as FULL-BAND reference lines UNDERNEATH the
                       box — A154, Marc's v18. OFF BY DEFAULT. ⚠️ The height and the z-order are
                       load-bearing rather than styling: they are what makes the coincident case
                       (`whisker_high == max_value`) readable as two marks instead of one
    extreme_line_opacity
                       the weight of those lines. `EXTREME_LINE_OPACITY` (the default) or
                       `EXTREME_LINE_OPACITY_LIGHTER` — Marc's two candidate weights, both shipped
                       because he named two and picking one for him is not this module's call
    value_labels_own_row
                       move the team's value label OUT of the axis label row — above the box for a
                       one-sided chart, into its own band below for two-sided — and draw it at
                       `VALUE_LABEL_FONT` rather than 9. OFF BY DEFAULT. ✅ It is what lets all four
                       of MIN/p25/p75/MAX survive, because the value label was displacing one
    """
    if row is None:
        return (f"<span class='cfdb-dist cfdb-dist-empty' style='width:{width}px' "
                f"title='cfdb holds no distribution for this week yet'>\u2013</span>")

    def num(key):
        raw = row.get(key)
        return None if raw is None or pd.isna(raw) else float(raw)

    def as_number(raw):
        return None if raw is None or pd.isna(raw) else float(raw)

    # ── A154: WHERE THE DECIMAL RULE LIVES ──────────────────────────────────────────────
    #
    # > **MARC, v18:** *"Don't use decimal points when displaying Yards. That includes Box/Whisker
    # > marks, axis labels … Exception is YDS/CARRY (#.#)"*
    #
    # ✅ **`fmt.precision_for` ALREADY ENCODES EXACTLY THIS AND HAS SINCE R-555** — its default is
    # 0 and a decimal is the keyed exception, which is Marc's sentence written as a table. 🚨 **The
    # chart never asked it.** `dp` defaulted to the literal `1`, so every axis label and every mark
    # was forced to one decimal whatever the metric was: `total_yards` printed `269.8`.
    #
    # ✅ SO THE KNOWLEDGE STAYS IN ONE PLACE (§4.2.1's question — how many places can a formatting
    # decision live before they disagree). A caller passes the metric NAME and the module asks;
    # a caller that passes `dp` explicitly still wins, and a caller that passes NEITHER gets the
    # old literal 1, which is what keeps every existing render byte-identical.
    if dp is _UNSET:
        dp = fmt.precision_for(metric) if metric else 1
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

    # 🚨 A142. A MARK DRAWN AT THE EXTREME HAS TO BE INSIDE THE viewBox, so the frame takes the
    # extremes the same way it takes the value markers — and for the same stated reason, which is
    # that clamping an outlier to the boundary tells the reader it is AT the extreme when it is
    # BEYOND it. ⚠️ NEVER BY DEFAULT: an unasked-for widening would move every chart the site
    # already draws, which is the one thing a default may not do.
    #
    # 🚨 A150 SPLIT THE WIDENING FROM THE RINGS, AND THE IMPLICATION ONLY EVER RAN ONE WAY.
    # A142's argument is *a ring implies widening*; it was written as `if outliers`, which also
    # made it *widening implies rings*. **Marc asked for the frame and said nothing about rings**
    # — v17: *"the boundaries of the chart should extend to the MIN and MAX"* — so the three
    # things that need the wider frame now ask for it independently:
    #
    #     outliers=True         a ring is drawn AT min/max, so it must be inside the box
    #     ticks=TICK_EXTREMES   a LABEL is drawn at min/max, same rule, same reason
    #     frame_extremes=True   the caller wants the range visible with no marks at all
    #
    # ⚠️ `min_value`/`max_value` ARE READ UNCONDITIONALLY NOW and that is free — two `row.get`s —
    # but they WIDEN only when one of the three asks. The reading and the widening were one
    # expression before, which is what welded the two features together.
    out_min, out_max = num("min_value"), num("max_value")
    # A154 adds the fourth way to ask: a full-height line AT min/max must be inside the
    # viewBox for the same reason A142 gave for a ring and A150 for a label.
    wants_extremes = (outliers or frame_extremes or ticks == TICK_EXTREMES
                      or extreme_lines)
    if wants_extremes:
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
    # ── A154: THE MIN/MAX REFERENCE LINES, AND THEY GO DOWN FIRST ────────────────────────
    #
    # > **MARC, v18:** *"MIN/MAX should extend full height of the plot (to the exten of the Box).
    # > Plot MIN/MAX below (underneath in the Z) so that if IQR and MIN/MAX are equal, should be
    # > able to discern both on the chart."*
    #
    # 🚨 THE LAST CLAUSE IS THE WHOLE POINT AND IT IS THE DEFECT HE REPORTED ONE ROUND AGO
    # (cfdb-main-R-1065): on a row where `whisker_high == max_value` he could not tell which mark
    # he was looking at, and the honest answer was *they are the same number*.
    #
    # ✅ **THE FIX IS GEOMETRY, NOT COLOUR.** A FULL-HEIGHT line drawn UNDERNEATH means that when
    # the two coincide the short whisker serif sits on top of a taller, lighter line and both
    # remain readable. ⚠️ **So the height and the z-order are load-bearing**: a mark drawn at serif
    # height, or appended after the box, fails his sentence exactly — which is why this block is
    # the FIRST thing in `parts` rather than the last.
    #
    # ⚠️ FULL HEIGHT IS THE PLOT BAND, `0..height`, not the rect. His parenthesis says *"to the
    # exten of the Box"*, and the box IS the plot here — the rect is `mid ± rect_half`, a little
    # over half the band, and a line stopping there would not clear the serifs it has to outlive.
    if extreme_lines:
        for extreme in (out_min, out_max):
            if extreme is None:
                continue
            parts.append(
                f"<line x1='{at(extreme):.1f}' y1='0' x2='{at(extreme):.1f}' "
                f"y2='{height:g}' stroke='currentColor' stroke-width='1' "
                f"opacity='{extreme_line_opacity:g}'></line>")

    # ⚠️ A154: `.55` → `WHISKER_OPACITY`. Marc asked for the structure 25% darker, globally — this
    # is not opt-in, because he asked for it on every chart rather than for a new capability.
    parts.append(f"<line x1='{at(lo):.1f}' y1='{mid:.1f}' x2='{at(hi):.1f}' y2='{mid:.1f}' "
                 f"stroke='currentColor' stroke-width='1' opacity='{WHISKER_OPACITY:g}'></line>")
    for end in (lo, hi):
        parts.append(f"<line x1='{at(end):.1f}' y1='{mid - serif_half:.1f}' x2='{at(end):.1f}' "
                     f"y2='{mid + serif_half:.1f}' stroke='currentColor' stroke-width='1' "
                     f"opacity='{WHISKER_OPACITY:g}'></line>")

    # The box: p25 to p75.
    # ⚠️ THE HEIGHT IS EMITTED AT ZERO DECIMALS AND THE y AT ONE, WHICH IS NOT AN OVERSIGHT: it is
    # what the pre-A145 literal `height='14'` did, and keeping it is what makes the default render
    # byte-identical. A rect's thickness is decoration and a whole pixel is enough of it.
    parts.append(f"<rect x='{at(p25):.1f}' y='{mid - rect_half:.1f}' "
                 f"width='{max(at(p75) - at(p25), 1):.1f}' "
                 f"height='{rect_half * 2:.0f}' fill='currentColor' fill-opacity='.14' "
                 f"stroke='currentColor' stroke-width='1' "
                 f"stroke-opacity='{BOX_OUTLINE_OPACITY:g}'></rect>")

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
    # ⚠️ A235: THE PLACEMENT RULE MOVED OUT AND NOTHING ABOUT IT CHANGED. `panel()` needs the
    # identical contest for its own axis band, and `_LabelBands` is this closure lifted verbatim
    # — `scale` is still 1.0 for every axis label and for every caller that has not asked for the
    # bigger value font, so the arithmetic here is unchanged for them to the bit.
    bands = _LabelBands(width, pad)
    place = bands.place

    # THE VALUE LABEL WINS, so it is placed into its band before anything else can take the room.
    #
    # 🚨 A154, AND IT IS THE FIX FOR A MEASUREMENT RATHER THAN A LOOK. > **MARC, v18:** *"Move the
    # label for the box-whisker line for displyaing for the team to be either a) above the box, or
    # below but inside the chart area (so that it doesn't compete for real estate with the the
    # min, p25, p75, max axis labels and we get axis labels for MIN, p25, p75, MAX on all the
    # box-whisker charts.)"*
    #
    # 📊 HE DIAGNOSED IT EXACTLY. `place()` is first-come-first-served and the value goes in FIRST,
    # so on a one-sided chart it takes room in the `below` band and a percentile is dropped —
    # which is why all four axis labels survived on only a third of rows (cfdb-main-R-1055).
    #
    # ✅ `value_labels_own_row` GIVES EACH VALUE ITS OWN ROW and leaves the axis row to the axis:
    #     one-sided   the value goes ABOVE the box
    #     two-sided   the above side stays above; the below side gets its own row BETWEEN the plot
    #                 and the axis labels — *"below but inside the chart area"*, and the axis row
    #                 moves down to make space rather than sharing
    #
    # ⚠️ OPT-IN, SO EVERY EXISTING CALLER RENDERS UNCHANGED (A145's rule). The page half is B128's;
    # this ships the capability, not a new layout nobody asked for.
    for marker_value, marker_label, marker_color, side, _title in markers:
        if value_labels_own_row:
            band = "above" if side != "below" else "value-below"
        else:
            band = "above" if side == "above" else "below"
        place(band, at(marker_value),
              marker_label if marker_label is not None
              else fmt.number(marker_value, dp=dp),
              marker_color,
              _VALUE_LABEL_SCALE if value_labels_own_row else 1.0)
    # ⚠️ A235: WHICH VALUES EACH STRATEGY LABELS, AND IN WHICH ORDER, IS NOW `_axis_ticks` — the
    # same list `panel()` reads. The strategy's meaning (whisker ends for every strategy but
    # `extremes`, Marc's MIN·MAX·p25·p75 priority for that one) is documented there, once.
    for edge in _axis_ticks(row, ticks):
        place("below", at(edge), fmt.number(edge, dp=dp))

    # ⚠️ THE BOX KEEPS ITS OWN COORDINATES AND THE BAND IS ADDED AROUND IT, so every line above
    # this point is written once and the one-value SVG is unchanged to the byte.
    #
    # ⚠️ A154: a one-sided chart needs a top band too once its value label lives above the box —
    # without it the label sits at y=-6 and the viewBox clips it.
    top_band = LABEL_BAND if (two_sided or value_labels_own_row) else 0
    # The second value's own row, between the plot and the axis labels. Only a two-sided chart
    # asking for the move needs it; everything else keeps today's geometry exactly.
    value_below_band = LABEL_BAND if (value_labels_own_row and two_sided) else 0
    # 🚨 AND THE FONT — Marc: *"Increase the font on the value being plotted for the team"*. The
    # axis labels stay at 9; the team's value goes to 11. ⚠️ A BIGGER LABEL CLAIMS MORE WIDTH from
    # the same budget the four axis labels compete for, which is why `_text_width` is asked for
    # the value at its OWN size below rather than at the axis size.
    for band, baseline in (("above", -6.0),
                           ("value-below", height + 11),
                           ("below", height + 11 + value_below_band)):
        for x, _half, text, color in bands.get(band):
            fill = f"fill='{color}'" if color else "fill='currentColor' opacity='.65'"
            # ⚠️ GATED ON THE FLAG, NOT ON `color`. A two-sided caller that has NOT asked for the
            # move also draws a coloured label in the `above` band — keying the size off the
            # colour would silently enlarge it and break A145's byte-identical default.
            size = (VALUE_LABEL_FONT
                    if value_labels_own_row and band in ("above", "value-below") and color
                    else 9)
            parts.append(f"<text x='{x:.1f}' y='{baseline:.1f}' text-anchor='middle' "
                         f"font-size='{size:g}' {fill}>{text}</text>")

    body = "".join(parts)
    if top_band:
        body = f"<g transform='translate(0,{top_band})'>{body}</g>"
    # ⚠️ `:g` ON THE THREE PLACES THIS IS EMITTED, AND IT IS THE DIFFERENCE BETWEEN A
    # BYTE-IDENTICAL DEFAULT AND 580 CHANGED RENDERS. `height` became a float so the ratios above
    # could be computed from it, which turned `41` into `41.0` in the viewBox and both attributes
    # — the ONLY thing A145's first draft changed at the default, and the hash comparison against
    # the pre-change module is what found it. `:g` prints 41 for 41.0 and 71.5 for 71.5.
    total_height = top_band + height + 15 + value_below_band

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
    return f"<span class='cfdb-dist' title='{_attr(describe(row))}'>{svg}</span>"


def render(html: str) -> None:
    """Write one of the above to the page."""
    st.markdown(html, unsafe_allow_html=True)
