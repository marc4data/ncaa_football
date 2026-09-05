"""Reusable plot builders for cfdb analysis notebooks.

WHY A MODULE RATHER THAN CHART CODE IN CELLS
--------------------------------------------
Two charts of the same kind in one notebook should be the same chart with different data.
Building them from these functions is what makes that true -- colors, gridlines, label
policy and figure size are decided once here, so a notebook cell says what it is plotting
and never how to plot it.

THE PALETTE IS VALIDATED, NOT CHOSEN
------------------------------------
`PALETTE` is a fixed eight-slot categorical order that passes lightness-band, chroma,
colorblind-separation and normal-vision-separation checks on the light surface below.
Two rules follow from that and are enforced here rather than left to the caller:

  * Slots are assigned IN ORDER and never cycled. A ninth series is not a ninth color --
    it folds into "Other", or the chart becomes small multiples.
  * `scatter()` caps at THREE hues. The eight-slot order is validated for adjacent pairs
    (bars, stacked segments, lines); a scatter puts every pair on screen at once, and only
    the first three clear the floors under that harder test.

Three slots (aqua, yellow, magenta) sit below 3:1 contrast on this surface, so every chart
that can carry a visible label does -- that is the relief, not a nicety.

OTHER STANDING RULES
--------------------
  * ONE value axis, always. Never `twinx()`: two scales in one frame invent correlations.
    Two measures of different magnitude are two charts, or one indexed to a common base.
  * Color follows the entity, not its rank -- `series_colors()` takes a stable key list so
    filtering a team out does not repaint the survivors.
  * Text wears ink tokens, never the series color.

Usage
-----
    import cfdb_plots as viz
    viz.set_style()

    fig, ax = viz.bar(df, "conference", "avg_margin", title="Average scoring margin, 2025")
    fig, ax = viz.line(df, "week", "margin", series="team", title="Margin by week")
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# --------------------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------------------

SURFACE = "#fcfcfb"          # the surface the palette was validated against
INK = "#0b0b0b"              # primary
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"        # axis labels, tick text
GRID = "#e1e0d9"             # hairline
AXIS = "#c3c2b7"             # baseline

# Fixed categorical order. Do not sort, shuffle or cycle this.
PALETTE: List[str] = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

# Slots validated for ALL pairs simultaneously -- the cap for scatter and bubble charts.
SCATTER_SLOTS = 3

# Single hue, light -> dark, for continuous magnitude.
SEQUENTIAL: List[str] = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6",
                         "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

# Two poles and a neutral middle, for signed quantities like point differential.
#
# RED IS THE NEGATIVE ARM. The palette names blue and red as the pair without saying which
# way round; on every measure in this warehouse -- margin, differential, ATS edge -- the
# negative side is the deficit, and a red deficit is what a reader already expects. Painting
# the winners red makes a correct chart read backwards at a glance.
DIVERGING = {"negative": "#e34948", "midpoint": "#f0efec", "positive": "#2a78d6"}

# Reserved. Never reuse these for a series.
STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}


def set_style() -> None:
    """Apply the cfdb chart defaults. Call once in the setup cell."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",

        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,

        # Recessive chrome: the data is the ink, the frame is not.
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": INK_SECONDARY,
        "axes.labelsize": 10,
        "axes.titlesize": 13,
        # "semibold" is not a weight these system faces ship, and matplotlib prints a
        # findfont warning on every single chart when it cannot resolve one.
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlelocation": "left",
        "axes.titlepad": 14,

        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.direction": "out",
        "ytick.direction": "out",

        "grid.color": GRID,
        "grid.linewidth": 0.8,

        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": INK_SECONDARY,

        "lines.linewidth": 2.0,
        "lines.markersize": 5.0,       # ~10px diameter
    })


def series_colors(keys: Sequence[Any]) -> Dict[Any, str]:
    """Stable key -> color map in fixed slot order.

    Pass the FULL key list (not the filtered one) so that hiding a series never repaints
    the rest. Beyond eight keys this raises rather than cycling: fold the tail into
    "Other" or facet the chart.
    """
    keys = list(dict.fromkeys(keys))
    if len(keys) > len(PALETTE):
        raise ValueError(
            f"{len(keys)} series exceeds the {len(PALETTE)}-slot palette. Cycling colors "
            f"makes two entities share one identity -- fold the tail into 'Other' with "
            f"top_n(), or draw small multiples."
        )
    return {key: PALETTE[i] for i, key in enumerate(keys)}


def team_colors(frame: pd.DataFrame, team_col: str = "team",
                color_col: str = "color_on_light") -> Dict[str, str]:
    """Brand colors carried by the serving views themselves.

    srv_standings, srv_team_game_log and srv_teams_index all expose `color_on_light`, which
    dbt has already contrast-checked against a light surface. Use this ONLY where team
    identity is the point (a two-team comparison, a conference of eight); a chart of
    twenty teams in twenty brand colors is unreadable no matter how the colors were picked,
    and the palette above is the better answer there.

    Teams with no dimension row -- non-FBS opponents exist as stubs -- fall back to muted
    ink rather than being dropped.
    """
    mapping = (frame[[team_col, color_col]].dropna(subset=[team_col])
               .drop_duplicates(subset=[team_col]))
    return {row[team_col]: (row[color_col] if isinstance(row[color_col], str)
                            else INK_MUTED)
            for _, row in mapping.iterrows()}


def top_n(frame: pd.DataFrame, by: str, n: int = 8, keep: str = "largest",
          label_col: Optional[str] = None, other: str = "Other") -> pd.DataFrame:
    """Keep the n most (or least) extreme rows and roll the rest into one 'Other' row.

    The honest way past the eight-slot ceiling: the tail is still on the chart, it just
    stops claiming individual identity.
    """
    ordered = frame.nlargest(n, by) if keep == "largest" else frame.nsmallest(n, by)
    rest = frame.drop(ordered.index)
    if rest.empty:
        return ordered
    label_col = label_col or [c for c in frame.columns if c != by][0]
    tail = pd.DataFrame([{label_col: other, by: rest[by].sum()}])
    return pd.concat([ordered, tail], ignore_index=True)


# --------------------------------------------------------------------------------------
# Chart builders
# --------------------------------------------------------------------------------------


def _finish(ax, title: Optional[str], subtitle: Optional[str],
            xlabel: Optional[str], ylabel: Optional[str], source: Optional[str]) -> None:
    """Titles, caption and the shared chrome every chart gets.

    The subtitle sits on the axes and the title is padded ABOVE it, rather than both being
    drawn at the frame top where they overlap. The source caption is figure-level and the
    layout reserves a strip for it, so it never lands on the tick labels.
    """
    if title:
        # 14pt of pad clears the axes; a subtitle needs a line's worth more.
        ax.set_title(title, pad=30 if subtitle else 14)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=10, color=INK_SECONDARY)
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel or "")
    if source:
        ax.figure.text(0.005, 0.005, source, ha="left", va="bottom",
                       fontsize=8, color=INK_MUTED)


def _layout(fig, source: Optional[str], legend_below: bool = False) -> None:
    """tight_layout, reserving a bottom strip for whatever has to live under the axes."""
    bottom = (0.04 if source else 0.0) + (0.07 if legend_below else 0.0)
    fig.tight_layout(rect=(0, bottom, 1, 1) if bottom else None)


def _formatter(values) -> "callable":
    """One number format for the whole series.

    Deciding per value gives '4.4' next to '4' in the same column, which reads as two
    different precisions rather than one rounded set.
    """
    numbers = [v for v in values if pd.notna(v)]
    whole = all(float(v) == int(v) for v in numbers) if numbers else True

    def fmt(value: float, decimals: int = 1) -> str:
        return f"{int(value):,}" if whole else f"{value:,.{decimals}f}"
    return fmt


def bar(frame: pd.DataFrame, category: str, value: str, *,
        title: Optional[str] = None, subtitle: Optional[str] = None,
        xlabel: Optional[str] = None, ylabel: Optional[str] = None,
        source: Optional[str] = None,
        horizontal: Optional[bool] = None, sort: bool = True,
        color: Optional[Any] = None, diverging: bool = False, labels: bool = True,
        decimals: int = 1, figsize: Optional[Tuple[float, float]] = None):
    """Magnitude across categories -- the default form for "which is biggest".

    Horizontal above six categories (long team and conference names do not fit under a
    vertical bar), and always direct-labeled: the value is on the mark, so no gridline or
    value axis is needed at all.

    `color` takes a single hex, or a dict from category to hex -- pass `team_colors(df)`
    for a team chart. `diverging=True` colors by SIGN instead, which is the honest encoding
    for a measure where zero means something: margin, point differential, ATS edge.
    """
    data = frame[[category, value]].dropna()
    if sort:
        data = data.sort_values(value, ascending=False)
    horizontal = len(data) > 6 if horizontal is None else horizontal
    if horizontal:
        data = data.iloc[::-1]  # largest at the top once the y axis is drawn upward

    if diverging:
        colors = [DIVERGING["positive"] if v >= 0 else DIVERGING["negative"]
                  for v in data[value]]
    elif isinstance(color, dict):
        colors = [color.get(k, INK_MUTED) for k in data[category]]
    else:
        colors = color or PALETTE[0]

    if figsize is None:
        figsize = (8, max(2.5, 0.34 * len(data) + 1.2)) if horizontal else (8, 4.5)
    fig, ax = plt.subplots(figsize=figsize)

    has_negative = bool((data[value] < 0).any())
    if horizontal:
        bars = ax.barh(data[category].astype(str), data[value], color=colors, height=0.68)
        ax.xaxis.grid(True, alpha=0.9)
        ax.set_axisbelow(True)
        ax.spines["bottom"].set_visible(False)
        # WITH NEGATIVES THE BASELINE IS ZERO, NOT THE FRAME EDGE. Left-spining a chart
        # whose bars run both ways draws the axis somewhere no bar starts, and every
        # length is then read from the wrong origin.
        if has_negative:
            ax.spines["left"].set_visible(False)
            ax.axvline(0, color=AXIS, linewidth=1.0, zorder=2)
    else:
        bars = ax.bar(data[category].astype(str), data[value], color=colors, width=0.68)
        ax.yaxis.grid(True, alpha=0.9)
        ax.set_axisbelow(True)
        if has_negative:
            ax.spines["left"].set_visible(False)
            ax.axhline(0, color=AXIS, linewidth=1.0, zorder=2)

    if labels:
        # Direct labels ARE the contrast relief for the lighter palette slots, so they are
        # on by default. With them present the value axis is redundant; drop it.
        fmt = _formatter(data[value])
        span = (data[value].max() - min(0, data[value].min())) or 1
        pad = 0.015 * span
        for rect, val in zip(bars, data[value]):
            # Outside the bar END, and the end of a negative bar is its left/bottom edge.
            offset = pad if val >= 0 else -pad
            if horizontal:
                ax.text(rect.get_width() + offset,
                        rect.get_y() + rect.get_height() / 2,
                        fmt(val, decimals), va="center",
                        ha="left" if val >= 0 else "right",
                        fontsize=9, color=INK_SECONDARY)
            else:
                ax.text(rect.get_x() + rect.get_width() / 2,
                        rect.get_height() + offset, fmt(val, decimals), ha="center",
                        va="bottom" if val >= 0 else "top",
                        fontsize=9, color=INK_SECONDARY)
        if horizontal:
            ax.xaxis.set_visible(False)
            ax.xaxis.grid(False)
            # Room for the outermost label, which tight_layout does not measure.
            ax.margins(x=0.12)
        else:
            ax.yaxis.set_visible(False)
            ax.yaxis.grid(False)
            ax.margins(y=0.12)

    _finish(ax, title, subtitle, xlabel, ylabel, source)
    _layout(fig, source)
    return fig, ax


def _spread(points: List[Tuple[str, Any, float]], ax, min_gap: float = 0.05):
    """Nudge end-of-line labels apart so two close finishes stay two readable words.

    Sorts by value and pushes each label up until it clears the one below by min_gap of
    the axis range. The label moves; the line and its marker do not, so nothing about the
    data is misstated -- only where the name is parked.
    """
    if len(points) < 2:
        return points
    low, high = ax.get_ylim()
    gap = min_gap * (high - low)
    ordered = sorted(points, key=lambda item: item[2])
    out = [list(item) for item in ordered]
    for i in range(1, len(out)):
        if out[i][2] - out[i - 1][2] < gap:
            out[i][2] = out[i - 1][2] + gap
    return [tuple(item) for item in out]


def line(frame: pd.DataFrame, x: str, y: str, *, series: Optional[str] = None,
         title: Optional[str] = None, subtitle: Optional[str] = None,
         xlabel: Optional[str] = None, ylabel: Optional[str] = None,
         source: Optional[str] = None, color: Optional[Any] = None,
         markers: bool = True, direct_labels: bool = True,
         figsize: Tuple[float, float] = (8, 4.5)):
    """Change over an ordered axis -- weeks, seasons, snapshots.

    Up to four series are direct-labeled at their last point AND carry a legend, so
    identity never rests on color alone. One series gets no legend: the title names it.
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax.yaxis.grid(True, alpha=0.9)
    ax.set_axisbelow(True)

    if series is None:
        ax.plot(frame[x], frame[y], color=color or PALETTE[0],
                marker="o" if markers else None, markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=1.5)
    else:
        keys = list(dict.fromkeys(frame[series]))
        palette = color if isinstance(color, dict) else series_colors(keys)
        endpoints = []
        for key in keys:
            part = frame[frame[series] == key].sort_values(x)
            ax.plot(part[x], part[y], color=palette[key], label=str(key),
                    marker="o" if markers else None, markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
            if not part.empty:
                last = part.iloc[-1]
                endpoints.append((str(key), last[x], last[y]))

        labelled = direct_labels and len(keys) <= 4
        if labelled:
            # Room on the RIGHT ONLY for the labels -- annotations are invisible to
            # tight_layout, and margins() would pad the left just as much for nothing.
            left, right = ax.get_xlim()
            ax.set_xlim(left, right + 0.15 * (right - left))
            for label_text, at_x, at_y in _spread(endpoints, ax):
                ax.annotate(f" {label_text}", (at_x, at_y), color=INK_SECONDARY,
                            fontsize=9, va="center", ha="left",
                            xytext=(4, 0), textcoords="offset points")

        # BELOW THE AXES when the lines are direct-labeled. Anywhere inside the frame the
        # box either sits on the data or lands in the end-label gutter and prints every
        # name twice; a row underneath collides with neither.
        if labelled:
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14),
                      ncol=min(4, len(keys)))
        else:
            ax.legend(loc="best")

    _finish(ax, title, subtitle, xlabel, ylabel, source)
    _layout(fig, source, legend_below=series is not None and direct_labels
            and frame[series].nunique() <= 4)
    return fig, ax


def scatter(frame: pd.DataFrame, x: str, y: str, *, hue: Optional[str] = None,
            label: Optional[str] = None, label_n: int = 0,
            title: Optional[str] = None, subtitle: Optional[str] = None,
            xlabel: Optional[str] = None, ylabel: Optional[str] = None,
            source: Optional[str] = None, size: float = 42.0,
            reference_line: bool = False,
            figsize: Tuple[float, float] = (7, 6)):
    """Relationship between two measures -- one dot per row.

    `hue` is capped at three categories on purpose: a scatter puts every color pair on
    screen simultaneously, and only the first three palette slots clear the colorblind and
    normal-vision separation floors under that test. Above three, facet instead.

    `label_n` direct-labels the n most extreme points on each axis rather than every point,
    which is what keeps a 130-team chart readable.
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax.grid(True, alpha=0.9)
    ax.set_axisbelow(True)

    if hue is None:
        ax.scatter(frame[x], frame[y], s=size, color=PALETTE[0],
                   edgecolor=SURFACE, linewidth=1.5, alpha=0.85, zorder=3)
    else:
        keys = list(dict.fromkeys(frame[hue]))
        if len(keys) > SCATTER_SLOTS:
            raise ValueError(
                f"{len(keys)} hues on a scatter; the all-pairs cap is {SCATTER_SLOTS}. "
                f"Facet with plt.subplots, or reduce the categories."
            )
        palette = series_colors(keys)
        for key in keys:
            part = frame[frame[hue] == key]
            ax.scatter(part[x], part[y], s=size, color=palette[key], label=str(key),
                       edgecolor=SURFACE, linewidth=1.5, alpha=0.85, zorder=3)
        ax.legend(loc="best")

    if reference_line:
        lo = min(frame[x].min(), frame[y].min())
        hi = max(frame[x].max(), frame[y].max())
        ax.plot([lo, hi], [lo, hi], color=AXIS, linewidth=1.2, linestyle="--",
                zorder=1, label=None)

    if label and label_n:
        extreme = pd.concat([
            frame.nlargest(label_n, y), frame.nsmallest(label_n, y),
            frame.nlargest(label_n, x), frame.nsmallest(label_n, x),
        ]).drop_duplicates()
        for _, row in extreme.iterrows():
            ax.annotate(str(row[label]), (row[x], row[y]), fontsize=8.5,
                        color=INK_SECONDARY, xytext=(6, 3), textcoords="offset points")
        ax.margins(0.10)

    _finish(ax, title, subtitle, xlabel, ylabel, source)
    _layout(fig, source)
    return fig, ax


def dist(values: Iterable[float], *, bins: int = 20,
         title: Optional[str] = None, subtitle: Optional[str] = None,
         xlabel: Optional[str] = None, ylabel: str = "games",
         source: Optional[str] = None, color: str = PALETTE[0],
         mean_line: bool = True, figsize: Tuple[float, float] = (8, 4.2)):
    """Shape of one measure. Fixed bin count so two runs are comparable."""
    data = pd.Series(list(values)).dropna()
    fig, ax = plt.subplots(figsize=figsize)
    ax.yaxis.grid(True, alpha=0.9)
    ax.set_axisbelow(True)
    ax.hist(data, bins=bins, color=color, edgecolor=SURFACE, linewidth=1.2, zorder=3)
    if mean_line:
        ax.axvline(data.mean(), color=INK_SECONDARY, linewidth=1.4, linestyle="--",
                   zorder=4)
        ax.annotate(f"mean {data.mean():,.1f}", (data.mean(), ax.get_ylim()[1]),
                    xytext=(6, -12), textcoords="offset points",
                    fontsize=9, color=INK_SECONDARY)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5, integer=True))
    _finish(ax, title, subtitle, xlabel, ylabel, source)
    _layout(fig, source)
    return fig, ax


def stat(value: Any, label: str, *, context: Optional[str] = None,
         color: str = INK, figsize: Tuple[float, float] = (3.2, 1.7)):
    """One number, big. The right form when a chart would plot a single value."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.axis("off")
    ax.text(0, 0.62, str(value), fontsize=34, color=color, va="center", ha="left")
    ax.text(0, 0.22, label, fontsize=10, color=INK_SECONDARY, va="center", ha="left")
    if context:
        ax.text(0, 0.02, context, fontsize=9, color=INK_MUTED, va="center", ha="left")
    fig.tight_layout()
    return fig, ax


def save(fig, name: str, directory: str = "figures"):
    """Write a figure beside the notebook. Returns the path so a cell can print it."""
    from pathlib import Path
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    path = out / (name if name.endswith(".png") else f"{name}.png")
    fig.savefig(path)
    return path
