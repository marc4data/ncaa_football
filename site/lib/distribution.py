"""ONE PICTURE, TWO SIZES. The standard way cfdb draws a distribution.

Marc: *"I want to have a standard way of showing. A good starting point for that method is in
`plot_distribution`."* — and *"It will be reusable call from several pages."*

So: one module, two entry points over the SAME row, and no page owns either.

    thumbnail(row)  ->  inline SVG, ~120x28, for a header bar
    panel(row)      ->  the full layout, for a page with room

ONE RENDERER, NOT TWO. An earlier draft had the thumbnail as inline SVG and the panel as
Vega-Lite. That is two implementations of one picture, which is the thing the bin edges are
fixed to prevent: two renderers drift, and the day they disagree the reader cannot tell which
is lying. The panel is the thumbnail with more room — same geometry, same code path, more
pixels — so a bug in the bars is one bug and a fix is one fix.

NO CHART LIBRARY. The site image's dependencies are streamlit, sqlalchemy, psycopg2-binary,
pandas, python-dotenv and openpyxl — no matplotlib, no altair, no plotly — and that list
carries a written warning about the cost of adding to it. Ten bars is about a dozen `<rect>`
elements, and the cards already emit raw HTML on every row, so this is a different string in a
path that exists.

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
    """
    if row is None:
        return "cfdb holds no distribution for this week yet"
    bits = [f"n={int(row['n'])} of {int(row['games_in_week'])} games"]
    for label, key in (("p25", "p25"), ("median", "p50"), ("p75", "p75")):
        value = row.get(key)
        if value is not None and not pd.isna(value):
            bits.append(f"{label} {fmt.number(float(value), dp=1)}")
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


def render(html: str) -> None:
    """Write one of the above to the page."""
    st.markdown(html, unsafe_allow_html=True)
