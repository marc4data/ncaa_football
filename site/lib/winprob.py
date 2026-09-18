"""The win-probability curve — the SVG, its scale, and the constants that tune it.

Promoted out of `views/today.py` by A170 (cfdb-main-R-1324) so the Matchup header can draw the
same chart. Marc, v20: *"Add the Win % chart to the right of the Scoreboard in the header"*.

🚨 B138 DID NOT ATTEMPT IT AND WAS RIGHT NOT TO: a view may not import a view, and `site/lib/`
is session A's. This is the fourth promotion of exactly that shape — `theme.viewer_is_dark`
(A165), `identity.player_row` (A167), `identity.split_name`/`card_text` (A167).

⚠️ THE MOVE IS VERBATIM. Every constant, comment and measurement below came across unchanged,
because each one records a render somebody looked at and re-deriving them would throw that away.
What changed is the NAMES of the five public entry points, and nothing else:

    sparkline_svg   was _sparkline_svg      the chart
    chart_width     was _curve_width        the natural width of one chart
    curve_label     was _curve_label        the "MICH 63%" text and whether the feed cut
    HEIGHT          was _CURVE_HEIGHT       the pinned height (cfdb-main-R-1249)
    PAD             was _CURVE_PAD

🚨 `chart_width`, NOT `width` — `sparkline_svg` has a local `width` and a same-named global
would shadow it into an UnboundLocalError. The bug is silent until the function runs.

✅ AND THE WIDTH IS EXPOSED RATHER THAN APPLIED, WHICH IS THE POINT OF PROMOTING IT PROPERLY.
`chart_width` exists because TEN charts on Today share one `table-layout:fixed` column and the
column must be sized to the widest of them — that is Today's constraint, and Today still owns
the `max(...)` that applies it. A Matchup header has ONE chart and no column, so it asks this
module for a width and decides for itself what to do with it. A promoted module that assumed
the shared column would hand Matchup a constraint that was never its own.
"""

import pandas as pd

from lib import fmt

# ── HOW DARK THE AXIS MARKS ARE, IN ONE PLACE (A138) ──────────────────────────────────────
#
# 🚨 MARC: "The axis marks need to be darker on the win probability chart." A122's precedent is
# exactly this class and it is the reason these are named rather than inlined: a band shaded at
# .07 was invisible, shipped looking finished, and .18 was chosen BY RASTERISING IT AT 4x AND
# LOOKING. A138 did the same and the before/after is in its report.
#
#     tick   .18 -> .32    quarter boundaries. The complaint.
#     major  (new) .55     halftime and the fourth quarter — Marc's own "(darker)"
#     zero   .35 -> .50    the even line, which is now the fill's baseline and carries more
#     fill   (new) .20     the area. Read at the same weight as the overtime band on purpose:
#                          neither may drown a tick, and the two are often adjacent.
_CURVE_TICK_OPACITY = .32
_CURVE_MAJOR_OPACITY = .55
_CURVE_ZERO_OPACITY = .50
_CURVE_FILL_OPACITY = .20
_CURVE_OT_SHADE_OPACITY = .18
_CURVE_OT_RULE_OPACITY = .8


# ── THE WIN-PROBABILITY CHART'S COORDINATE SYSTEM (A138, cfdb-main-R-905) ──────────────────
#
# 🚨 SHARED SCALE, NOT SHARED EXTENT, AND MARC'S TWO SENTENCES BOTH SURVIVE IT.
# "Y axis should be consistent across all rows" and "Games with overtime will be longer"
# cannot both hold if every chart is the same width — one of them has to give. They both hold
# if what is shared is the PIXELS PER SECOND: a quarter boundary lands at the same offset on
# every row, and an overtime game's chart is physically wider because it contains more game.
#
# 📊 A136 MEASURED THE ALTERNATIVE AND IT IS EXPENSIVE. Sizing every chart to the week's
# longest game spends 15.8-42.9% of a regulation chart's width on emptiness; in 2026 week 2 —
# the only week of 33 that reaches three overtimes — that is 84 charts paying for two.
_CURVE_REGULATION_UNITS = 3600          # seconds of regulation, and the axis unit itself
_CURVE_PX_PER_UNIT = 176.0 / 3600.0     # the SHARED SCALE. 176px of regulation, as before.
# ⚠️ ONE OVERTIME PERIOD IS DRAWN A QUARTER WIDE, AND THE NUMBER IS ARGUED RATHER THAN PICKED.
# A122's complaint was density: on the `play_number` axis Wake Forest at Purdue's 24 overtime
# plays occupied 20px of 180, about 0.8px a play against regulation's 1.0. A quarter's width is
# 44px, so those same 24 plays get 1.8px each — denser than regulation rather than sparser,
# which is the right way round for the part of the game that decided it.
_CURVE_OT_BAND_UNITS = 900
# ── ROOM AT THE RIGHT FOR THE FINAL LABEL, MEASURED RATHER THAN GUESSED (A139) ────────────
#
# 🚨 THE LABEL IS MONOSPACE ON PURPOSE, AND THAT IS WHAT MAKES ITS WIDTH A MEASUREMENT RATHER
# THAN A TABLE. A133 needed a per-character advance table for `distribution.py` because that
# text is proportional and `1` is not `8`. Setting this one in the same monospace stack every
# numeric column on the page already uses makes EVERY character the same width, so the whole
# question collapses to one number.
#
# 📊 MEASURED IN THE BROWSER at `font-size:9` in `ui-monospace,SFMono-Regular,Menlo,monospace`,
# via `getComputedTextLength()`: `M`, `i` and `%` all return **5.422px**, and `MICH 100%`
# returns 48.781 for nine characters — 5.4201 each. That uniformity IS the property being
# relied on, so it is recorded rather than assumed.
# 🚨 A167 (cfdb-main-R-1311). THE QUARTER LABELS SIT INSIDE THE PLOT, AND THE REASON IS A
# NUMBER MARC GAVE THIS PROJECT ONE ROUND AGO.
#
# > **MARC, v06:** *"label the x-axis with the quarters (1Q, 2Q, etc)."*
#
# ⚠️ **LABELS BELOW THE PLOT MAKE THE CHART TALLER, AND A165 SPENT A ROUND MAKING THIS ROW
# SHORTER AT HIS OWN REQUEST** — 94.2px -> 79.8px, because he asked for *"things more dense
# vertically"*. 📊 Measured both ways and reported to him: **inside costs 0px; below costs 14px
# per row, ~140px per panel**, which gives back most of what that round returned.
#
# ✅ **THE BOUNDARIES WERE ALREADY DRAWN AND HE IS ASKING FOR THEM TO BE NAMED** — the rules at
# 0/900/1800/2700/3600 have been there since A138. This adds the word, not the line.
#
# ⚠️ **AND OVERTIME IS NOT A QUARTER.** The label reads `OT`, `2OT`, `3OT` … per band, because
# the CHART draws a band per overtime period even though the SCOREBOARD collapses them into one
# column (`_quarter_cells`: *"one overtime column, not one per period"* — the data has no
# per-overtime breakdown, but the chart's x axis genuinely has the time). **A sequence reading
# `1Q 2Q 3Q 4Q 5Q` would be wrong and this is what stops it.**
# 🚨 A167: the final percentage is bigger than the 9px label it sits in — Marc's *"Increase the
# font of the final win %"*. 11.5 against 9 is a visible step without the number outgrowing the
# 64px chart it has to sit inside; it is anchored at its right edge so it costs no width.
_CURVE_FINAL_SIZE = 11.5
_CURVE_QUARTER_LABEL_SIZE = 6.5
_CURVE_QUARTER_LABEL_OPACITY = .45

_CURVE_LABEL_CHAR_PX = 5.4219
# The gap between the last point and the first glyph, and a little air after the last one.
_CURVE_LABEL_OFFSET = 4.0
LABEL_TRAIL = 2.0
_CURVE_LABEL_FONT = "ui-monospace,SFMono-Regular,Menlo,monospace"


def _curve_axis_units(points: pd.DataFrame) -> pd.Series:
    """Where each play sits on the chart's x axis, in axis units.

    🚨 TWO PUBLISHED COORDINATES, NEVER ADDED AND NEVER COALESCED — A136 built them that way
    and asserted it in dbt:

        regulation   `elapsed_from_kickoff_seconds`, 0…3600. NULL for every overtime play.
        overtime     `overtime_axis_offset_periods`, in OVERTIME PERIODS. NULL in regulation.

    They are never both populated on one row (0 of 291,548) and they are in different units,
    so the overtime one is scaled onto this axis by ONE page constant — §4.2.1's permitted
    shape, the same one `sx`/`sy` have always been. Combining two published columns would not
    be.

    ⚠️ A PLAY WITH NO PERIOD HAS NO POSITION ON A CLOCK AXIS, and gets NaN here rather than a
    guess. Exactly one play of 291,548 is in that state — the one with no `stg_play` match —
    and it is dropped from the line rather than placed somewhere it was not. AC-G.32: an
    unknown is not a zero and is not the end of the game.
    """
    elapsed = pd.to_numeric(points["elapsed_from_kickoff_seconds"], errors="coerce")
    offset = pd.to_numeric(points["overtime_axis_offset_periods"], errors="coerce")
    return elapsed.where(
        elapsed.notna(),
        _CURVE_REGULATION_UNITS + offset * _CURVE_OT_BAND_UNITS)


PAD = 2
# 🚨 A164 (cfdb-main-R-1142). THE HEIGHT IS A MEASUREMENT OF THE CELL BESIDE IT, NOT A TASTE.
# Marc, Today v04: *"Win Probability needs to take up more vertical space. Stretch the y-axis to
# take up the same amount of space by the Away and Home lines in the Scoreboard."*
#
# 📊 MEASURED IN CHROMIUM ON THE REAL PANEL at a 1300px viewport, by class rather than by
# position — `.cfdb-sb-away` top 767.7px to `.cfdb-sb-home` bottom 834.9px = **67.2px**. The
# thead ("1 2 3 4 F") is NOT part of that span and an earlier reading that included it said 80.8.
#
# ⚠️ AND 67 IS THE ONE HEIGHT THAT CANNOT MAKE THE ROW GROW, which is why "the same space" is a
# safe ask where "more space" would not have been. The row is 94.2px: the scoreboard's own 80.8
# plus `.cfdb-table td`'s 6.72px of padding top and bottom. A chart at 67px sits inside that
# content box with room to spare; a chart taller than 80.8 would re-lay out every scoreboard on
# the page. ⚠️ The plotting band is `height - 2 * PAD`, so this takes it from 40.0 to 63.0.
# ⚠️ A165: 67 -> 64. The scoreboard's own vertical cell padding went to zero this round
# (cfdb-main-R-1302), which took `.cfdb-sb-away` top to `.cfdb-sb-home` bottom from 67.2px to
# **64.0px** — re-measured in Chromium by class, not adjusted by the same amount as the row.
# 🚨 **THIS CONSTANT IS PINNED, NOT DERIVED, AND THAT IS THE THING TO KNOW ABOUT IT.** Nothing
# computes it at render time, so any change to the scoreboard's geometry leaves it silently
# wrong and a test is the only thing that can say so — which is why
# `test_the_curve_is_as_tall_as_the_scoreboard_rows_it_sits_beside` carries the measured number
# and an upper bound rather than a range.
HEIGHT = 64


def _curve_final_value(points: pd.DataFrame):
    """The home win probability at the LAST PLOTTED play, or None.

    ⚠️ "Last plotted" rather than "last row": a play with no period has no position on a clock
    axis and is dropped from the line, so the label has to read the same filtered frame the
    curve does or it would name a point that is not on the chart.
    """
    if points is None or points.empty:
        return None
    plotted = points[_curve_axis_units(points).notna()]
    if plotted.empty:
        return None
    value = plotted["home_win_probability"].iloc[-1]
    return None if pd.isna(value) else float(value)


def curve_label(row, points) -> tuple:
    """`(text, is_cut)` for the mark at the end of the curve. ONE definition, two consumers.

    🚨 cfdb-main-R-934. THE LABEL USED TO BE A BARE PERCENTAGE AND IT SAT BESIDE THE WRONG TEAM'S
    NAME. Row 1 of 2026 week 2 read `IOWA STATE … / IOWA …` with `94%` against it — and the 94%
    is IOWA's, the HOME side, while the scoreboard deliberately puts the AWAY team on the top
    line (R-522). Every label was correct and the panel still told a reader the opposite of the
    truth. ⚠️ The `aria-label` already said *"Home win probability"*, so a screen-reader user was
    told which side it was and a sighted reader was not — an inversion of the usual failure.

    ✅ THE FIX IS THE HOME SIDE'S ABBREVIATION IN FRONT OF THE NUMBER, and the other two
    candidates were rejected for reasons rather than taste:

        label the WINNER          ❌ DISQUALIFIED BY THE GEOMETRY. The curve is home-perspective
                                  and the label sits at the last point's own height, so when the
                                  away side won the number would read 96% while sitting at the
                                  BOTTOM of the chart, where the home curve ended at 4%. A label
                                  that contradicts its own position is worse than a bare one.
        anchor it to the home row ❌ Moves the label away from the point it labels, and vertical
                                  alignment is not something a reader decodes as "this is the
                                  home team's number" while scanning ten rows.
        the abbreviation          ✅ Same glyph run as the number, so it survives greyscale and
                                  thumbnailing; agrees with the geometry (above the even line is
                                  home); and agrees with the `aria-label`, which now names the
                                  team rather than the role.

    📊 COVERAGE MEASURED IN PUBLISHED SERVING RATHER THAN ASSUMED: `home_abbreviation` is null on
    **0 of the 1,895 games that can enter this panel**, longest **4 characters**, mean 3.3. It is
    null on 4.9% of `srv_game` as a whole and reaches 9 characters on 22 rows there, none of
    which can be ranked here. ⚠️ A130's chain ends in "drop the suffix rather than print `None`";
    the same applies — with no abbreviation the label falls back to the bare percentage, and the
    `aria-label` still names the side.

    ⚠️ THE CUT CASE KEEPS ITS OWN SHAPE. There is no value to attribute to anybody, so it stays
    the single word and does not grow a team name in front of it.
    """
    reaches = row.get("win_probability_curve_reaches_final_score")
    if not (bool(reaches) if pd.notna(reaches) else True):
        return ("cut", True)
    final = _curve_final_value(points)
    if final is None:
        return ("", False)
    side = row.get("home_abbreviation")
    side = None if side is None or pd.isna(side) else str(side).strip()
    percent = f"{final * 100:.0f}%"
    return ((f"{side} {percent}" if side else percent), False)


def _curve_bands(points: pd.DataFrame) -> int:
    """How many overtime periods this game's curve spans. 0 for a regulation game."""
    if points is None or points.empty or "overtime_period" not in points:
        return 0
    periods = pd.to_numeric(points["overtime_period"], errors="coerce")
    return int(periods.max()) if periods.notna().any() else 0


def chart_width(points: pd.DataFrame) -> int:
    """This game's chart width in pixels, at the shared scale.

    🚨 THE PANEL NEEDS THIS BEFORE IT RENDERS ANY ROW, which is why it is its own function.
    `.cfdb-table` is `table-layout:fixed`: with no colgroup every column takes an equal share,
    and a chart that is wider than its share overflows the cell rather than shrinking. Reading B
    makes the charts differ in width on purpose, so the column has to be the widest of them —
    and that is a fact about the FRAME, not about any one row.

    ⚠️ A139 MADE THE GUTTER DEPEND ON THE LABEL RATHER THAN ON A CONSTANT, because naming the
    home side made the label variable. 🚨 **A164 REMOVED THE GUTTER ALTOGETHER AND WITH IT THAT
    PARAMETER**: the label is now drawn INSIDE the plot, to the left of the final point, so no
    width here depends on its length. A139's reasoning was right for a label in the margin and
    stops applying the moment the label leaves the margin. 📊 The effect is the one Marc asked
    for — a regulation chart goes from 224px to 182px, and the column is sized from the widest.
    """
    span = _CURVE_REGULATION_UNITS + _curve_bands(points) * _CURVE_OT_BAND_UNITS
    # 🚨 A164: THE LABEL NO LONGER BUYS A GUTTER, BECAUSE IT NO LONGER SITS IN ONE. It is drawn
    # to the LEFT of the final point, inside the plot, so the width is the span plus the trailing
    # margin and nothing else. ⚠️ A139's per-row gutter — sized from the label's own length — is
    # what this removes, and removing it is the POINT rather than a side effect: Marc asked for
    # the panel to get narrower and the column is `max(chart_width(...)) + 12`.
    return int(round(PAD * 2 + span * _CURVE_PX_PER_UNIT + LABEL_TRAIL))


def sparkline_svg(points: pd.DataFrame, label: str = "", is_cut: bool = False,
                  height: int = HEIGHT) -> str:
    """One game's win-probability curve, as inline SVG sized for a table cell.

    🚨 A CHART CANNOT LIVE INSIDE `table.render`, WHICH IS WHY THIS IS SVG AND NOT ALTAIR.
    `table.render` emits HTML and `st.altair_chart` is a Streamlit call; a cell cannot contain
    one. ⚠️ A138 RE-ASKED THIS RATHER THAN INHERITING IT, because the scoreboard change could
    have moved the container — and the answer is unchanged, because the container did not move.
    The scoreboard became one CELL of the same table, not a replacement for it, so the ten
    games still sit side by side in one grid and a sparkline is still the only mark that keeps
    that. ⚠️ `_scatter_svg` in this same file is the precedent: hand-drawn inline SVG in
    `currentColor`.

    🚨 THE X AXIS IS THE ELAPSED CLOCK, AND IT USED TO BE `play_number`. The docstring this
    replaces said `play_number` was "monotonic, unique within a game, no restarts" — and
    cfdb-main-R-916 measured that false: **795 consecutive pairs step BACKWARDS on the clock,
    across 336 of 1,898 games (17.7%)**, worst single back-step −3,567 seconds. Game 401635615
    has fourth-quarter plays at `play_number` 0–3 and a first-quarter play at 4, so its line
    crossed the whole width backwards with every point real. A comment asserting a property the
    warehouse does not have is worse than no comment, because the next reader trusts it.

    ⚠️ ORDER FOLLOWS THE COORDINATE, NOT `play_number` — see `_win_probability_curves`. Inside
    an overtime period `play_number` is the only order a play has, and there it is still used.

    🚨 THE COORDINATE MAPPING BELOW IS ARITHMETIC IN A PAGE FILE, AND IT IS NOT R-611's CLASS.
    §4.2.1's test is HOW MANY CONSUMERS A NUMBER CAN HAVE: `sx`/`sy` turn an axis position and
    a probability into pixel offsets inside this one <svg>, and a pixel offset is not a quantity
    anybody can cite, export, sort on or disagree with. ✅ THE SAME GOES FOR THE SIGNED AXIS.
    Marc asked for −1…1; the published column is 0…1 and the transform is `2p − 1`. That is a
    COORDINATE, not a fact about football — nobody can export "the home side was at +0.42" —
    so it lives here beside `sx`/`sy` rather than in dbt.

    📊 AND THE SIGNED AXIS CHANGES NO PIXEL, WHICH IS WORTH SAYING PLAINLY RATHER THAN LETTING
    A READER ASSUME OTHERWISE: `sy` already mapped an ABSOLUTE 0…1 onto the full height, so the
    y axis was ALREADY consistent across rows and 2p−1 onto −1…1 is the identical mapping. What
    actually changes is that the mid line is now ZERO and the curve is FILLED FROM IT — which is
    the point. Fill from zero makes the SIGN the picture, and above-or-below-zero is POSITION,
    so it survives greyscale (AC-G.22). The fill is decoration on a signal that already works
    without it — A131's argument for the two-sided box, one panel over.

    ⚠️ `sy` FLIPS AND MUST KEEP FLIPPING — SVG y grows downward and a home side at 1.0 belongs
    at the top. `_scatter_svg` in this same file deliberately does not flip and says why; the
    two sit in one file, so each states which it is.

    ❌ NO SMOOTHING, NO INTERPOLATION, NO ROLLING AVERAGE — every published point is plotted.
    The spikes ARE the drama and this panel exists to show them; a smoothed win-probability
    curve is a different claim about the game, and an AREA chart of a smoothed curve is the same
    different claim with more ink on it.
    """
    if points is None or points.empty:
        return fmt.EM_DASH

    pad = PAD
    units = _curve_axis_units(points)
    plotted = points.assign(_x_units=units)
    plotted = plotted[plotted["_x_units"].notna()]
    if plotted.empty:
        return fmt.EM_DASH

    # THE WIDTH IS THE GAME'S OWN LENGTH AT THE SHARED SCALE. A regulation game ends at 3600
    # units; each overtime period adds a band. Nothing is padded out to match another row.
    bands = _curve_bands(plotted)
    span_units = _CURVE_REGULATION_UNITS + bands * _CURVE_OT_BAND_UNITS
    width = chart_width(plotted)
    ph = height - 2 * pad

    def sx(axis_units) -> float:
        return pad + float(axis_units) * _CURVE_PX_PER_UNIT

    def sy(probability) -> float:
        # 🚨 A169 (cfdb-main-R-1318). THIS COMMENT SAID "−1…1 with zero in the middle" AND THE
        # FUNCTION HAS NEVER TAKEN −1. It takes `home_win_probability`, straight off
        # `srv_game_win_probability_play`, on **0…1**: `sy(1)` is the top, `sy(0)` the floor,
        # `sy(0.5)` the midline. Fed −1 it would return `pad + 2*ph` — a whole band BELOW the
        # chart. The −1…1 framing is what the FILLED-FROM-MIDLINE picture says to a reader; it
        # is not this function's domain, and the two were written as if they were the same.
        # **Seventh wrong-or-expired comment found in seven rounds.**
        #
        # ⚠️ **AND THE AXIS IS FIXED, WHICH IS THE THING MARC ASKED ABOUT (Site v07):** *"It
        # looks like it's auto-adjusting to fill the vertical space."* 📊 **It is not, and that
        # was measured rather than argued.** Two 2026 games rendered side by side:
        #
        #     401858447  win probability 0.747 … 1.000   curve spans 30.0px
        #     401862702  win probability 0.006 … 0.970   curve spans 57.9px
        #     midline in BOTH                            y = 32.0
        #
        # **An auto-fitting axis would stretch the first to fill the band and both spans would
        # match. They do not.** Nothing here reads the series' min or max — `sy` is a pure
        # function of one probability, pinned by
        # `test_the_win_probability_axis_is_fixed_and_reads_no_data`.
        #
        # 📊 **WHAT HE IS SEEING IS HIS OWN TWO ASKS.** `ph = height − 2*pad`, and `height` grew
        # twice at his request — A165 44 → 67 to match the scoreboard's two rows, A167 → 64 for
        # the quarter labels. **The band went 40px → 60px, so the same swing now draws 1.50× the
        # pixels it did three rounds ago** (measured on one game: 38.6px → 57.9px).
        return pad + (1.0 - float(probability)) * ph

    right = sx(span_units)
    zero = sy(0.5)
    parts = []

    # ── REFERENCE LINES ───────────────────────────────────────────────────────────────────
    #
    # 🚨 MARC NAMED FIVE REGULATION MARKS AND THE CLOCK HAS FOUR BOUNDARIES. "Start, 2nd, half,
    # 3rd, 4th" is what a broadcast shows, where halftime is an INTERVAL and the third quarter
    # begins after it. On an elapsed-clock axis "half" and "3rd" ARE THE SAME INSTANT — 1800
    # seconds — so five names map to four distinct quarter starts:
    #
    #     Start          0      kickoff
    #     2nd          900      the second quarter begins
    #     half / 3rd  1800      halftime AND the third quarter, one line carrying both names
    #     4th         2700      the quarter this panel's whole ordering is about
    #     (end)       3600      regulation ends; where overtime begins if there is any
    #
    # ✅ SO FIVE MARKS ARE DRAWN, NOT FOUR, and the fifth is the end of regulation rather than
    # an invented boundary. Marc's "Final" is the labelled end of the curve, below.
    #
    # ⚠️ AND THE EMPHASIS IS MARC'S OWN — "half (darker)", "4th (full, darker)". 1800 carries
    # two of his names and 2700 opens the quarter this panel ranks on, so those two are the
    # heavy ones.
    for at_units, weight, opacity in ((0, .5, _CURVE_TICK_OPACITY),
                                      (900, .5, _CURVE_TICK_OPACITY),
                                      (1800, .9, _CURVE_MAJOR_OPACITY),
                                      (2700, 1.1, _CURVE_MAJOR_OPACITY),
                                      (3600, .5, _CURVE_TICK_OPACITY)):
        if at_units > span_units:
            continue
        x = sx(at_units)
        parts.append(f"<line x1='{x:.1f}' y1='{pad}' x2='{x:.1f}' y2='{height - pad}' "
                     f"stroke='currentColor' stroke-width='{weight}' "
                     f"opacity='{opacity}'></line>")

    # ── OVERTIME: A SHADED BAND AND A HEAVY DIVIDER PER PERIOD ────────────────────────────
    #
    # ⚠️ SHADED FIRST, SO IT SITS UNDER THE LINE. A118 measured Jacksonville State at Ohio: TWO
    # fourth-quarter lead changes and ELEVEN in overtime. On an unmarked curve that reads as one
    # very long fourth quarter — the drama attributed to the wrong part of the game, with every
    # point still real.
    #
    # 🚨 THE DIVIDER IS PER PERIOD NOW, NOT ONE AT THE START OF OVERTIME. Each overtime period
    # has its own band and its own boundary, because each resets the clock and alternates
    # possession. A136 proved the arithmetic that makes this land exactly: the reference line
    # for overtime k falls on offset k − 1, so it sits exactly on the band edge.
    if bands:
        ot_start = sx(_CURVE_REGULATION_UNITS)
        parts.append(f"<rect x='{ot_start:.1f}' y='{pad}' "
                     f"width='{right - ot_start:.1f}' height='{ph}' "
                     f"fill='currentColor' opacity='{_CURVE_OT_SHADE_OPACITY}'></rect>")
        for band in range(bands):
            x = sx(_CURVE_REGULATION_UNITS + band * _CURVE_OT_BAND_UNITS)
            # ⚠️ DELIBERATELY HEAVIER THAN A QUARTER TICK. Overtime is a different KIND of
            # boundary from a quarter change and must not read as one more tick.
            parts.append(f"<line x1='{x:.1f}' y1='{pad}' x2='{x:.1f}' y2='{height - pad}' "
                         f"stroke='currentColor' stroke-width='1.4' "
                         f"opacity='{_CURVE_OT_RULE_OPACITY}'></line>")

    # ── ZERO. The only reference point on the whole picture, and now the fill's baseline. ──
    parts.append(f"<line x1='{pad}' y1='{zero:.1f}' x2='{right:.1f}' y2='{zero:.1f}' "
                 f"stroke='currentColor' stroke-width='.6' "
                 f"opacity='{_CURVE_ZERO_OPACITY}' stroke-dasharray='2 2'></line>")

    # ── THE CURVE ─────────────────────────────────────────────────────────────────────────
    #
    # 🚨 STILL BROKEN AT EVERY OVERTIME BOUNDARY, AND A138 RE-DECIDED IT RATHER THAN INHERITING
    # IT. The original reason was density — `play_number` compressed overtime into a 20px sliver
    # and a wash was not legible — and the new coordinate removes that reason: overtime now
    # starts exactly where regulation ends and gets a quarter's width. ✅ THE OTHER REASON
    # STANDS ON ITS OWN AND IS WHY THE BREAK SURVIVES: overtime IS discontinuous football. The
    # clock resets, possession alternates, and the curve genuinely does not continue from the
    # fourth quarter's last play. A filled area that ran straight through would draw one
    # continuous game where there were two.
    #
    # ⚠️ AND NO POINT MOVES TO ACHIEVE IT. A stroke weight is a rendering property; a coordinate
    # is a claim about when something happened.
    #
    # ⚠️ `is True` RATHER THAN TRUTHINESS. A null `is_overtime` is UNKNOWN: read as regulation it
    # would draw a break that did not happen, read as overtime it would suppress the real one.
    # Compared this way it does neither — it never triggers a transition. AC-G.32.
    # ONE PASS, carrying the previous play's band — not a lookup per point. The first draft
    # re-filtered the frame for every play, which is the O(n^2) shape A097 and A120 both paid for.
    segments, current, previous_band = [], [], None
    for axis_units, probability, in_overtime, ot_period in zip(
            plotted["_x_units"], plotted["home_win_probability"],
            plotted["is_overtime"], plotted.get("overtime_period", plotted["_x_units"] * 0)):
        now_overtime = in_overtime is True or in_overtime == 1
        band = int(ot_period) if (now_overtime and pd.notna(ot_period)) else 0
        if band != previous_band and previous_band is not None and current:
            segments.append(current)
            current = []
        current.append((sx(axis_units), sy(probability)))
        previous_band = band
    segments.append(current)

    for index, coords in enumerate(segments):
        if len(coords) < 2:
            continue
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        # THE AREA, FILLED FROM ZERO. One closed path down to the baseline at each end: the
        # lobes above and below fill on their own sides, so the sign is the shape.
        area = (f"M{coords[0][0]:.1f},{zero:.1f} "
                + " ".join(f"L{x:.1f},{y:.1f}" for x, y in coords)
                + f" L{coords[-1][0]:.1f},{zero:.1f} Z")
        parts.append(f"<path d='{area}' fill='currentColor' "
                     f"opacity='{_CURVE_FILL_OPACITY}' stroke='none'></path>")
        is_overtime_segment = index > 0
        parts.append(
            f"<polyline points='{line}' fill='none' stroke='currentColor' "
            f"stroke-width='{1.8 if is_overtime_segment else 1.1}' "
            f"opacity='{1.0 if is_overtime_segment else 0.85}'></polyline>")

    # ── THE FINAL VALUE, AND THE ONE ABSENCE THAT MATTERS (AC-G.11) ───────────────────────
    #
    # 🚨 99 OF 1,898 CURVES NEVER REACH THEIR OWN GAME'S FINAL SCORE — CFBD's feed truncates,
    # and `srv_game.win_probability_curve_reaches_final_score` says which. A136 measured the
    # consequence and A138 measured how often a reader would actually meet it: **38 of 337
    # top-ten rows across 35 season-weeks, in 22 of those weeks, including two #1 rows.** This
    # is not a defensive branch; it is one row in nine.
    #
    # ❌ SO A TRUNCATED CURVE IS NOT LABELLED WITH A FINAL VALUE, because the number is not one.
    # Coastal Carolina at UTSA ends at 0.1% for a side that won 44-15; printing "0%" beside it
    # would be a confident wrong number a reader cannot tell from a real collapse.
    # ✅ IT IS STILL DRAWN — the first four fifths of the curve are real and dropping them would
    # lose more than it protects — and the end of the line is cut with a dashed rule and the word
    # so the absence says WHICH absence it is.
    # 🚨 A167: NAME THE QUARTERS. Centred in each band, on the floor of the plot, at low opacity
    # so the curve stays the thing being read. `dominant-baseline` is not used — it is
    # inconsistently supported in older renderers — so the baseline is placed explicitly.
    for index in range(4):
        centre = sx(_CURVE_REGULATION_UNITS / 8 * (2 * index + 1))
        parts.append(
            f"<text x='{centre:.1f}' y='{height - pad - 1.0:.1f}' text-anchor='middle' "
            f"font-size='{_CURVE_QUARTER_LABEL_SIZE}' font-family='{_CURVE_LABEL_FONT}' "
            f"fill='currentColor' opacity='{_CURVE_QUARTER_LABEL_OPACITY}'>{index + 1}Q</text>")
    for band in range(bands):
        centre = sx(_CURVE_REGULATION_UNITS + _CURVE_OT_BAND_UNITS * (band + 0.5))
        parts.append(
            f"<text x='{centre:.1f}' y='{height - pad - 1.0:.1f}' text-anchor='middle' "
            f"font-size='{_CURVE_QUARTER_LABEL_SIZE}' font-family='{_CURVE_LABEL_FONT}' "
            f"fill='currentColor' opacity='{_CURVE_QUARTER_LABEL_OPACITY}'>"
            f"{'' if band == 0 else band + 1}OT</text>")
    last_x, last_y = segments[-1][-1] if segments and segments[-1] else (right, zero)
    # ⚠️ CLAMPED INTO THE BOX. A game that ends at 100% puts its last point on the top edge, and
    # a baseline placed 3px below it still hangs the glyphs above the viewBox — where they are
    # clipped by the cell, not by the SVG, so it looks like a rendering bug. Found by rasterising.
    label_y = min(max(last_y + 3.0, pad + 7.0), height - pad - 1.0)
    if is_cut:
        parts.append(f"<line x1='{last_x:.1f}' y1='{pad}' x2='{last_x:.1f}' "
                     f"y2='{height - pad}' stroke='currentColor' stroke-width='1' "
                     f"opacity='.5' stroke-dasharray='1 2'></line>")
        described = ("Win probability by play, home side; the feed stops before the end of the "
                     "game, so there is no final value")
    else:
        described = (f"Win probability by play, home side, ending at {label}" if label
                     else "Win probability by play, home side")
    if label:
        # 🚨 MONOSPACE, AND IT IS NOT A STYLE CHOICE — see `_CURVE_LABEL_CHAR_PX`. Every glyph
        # is 5.4219px wide at this size, which is what lets `chart_width` size the gutter
        # exactly rather than from an advance table. It also matches `.cfdb-num`, so the label
        # reads as one more figure on a page of figures.
        # 🚨 A164: THE LABEL SITS TO THE LEFT OF THE FINAL POINT — Marc, Today v04, and his
        # second sentence is an ACCEPTANCE CRITERION rather than a rationale: *"That will
        # tighten up the horizontal space."* Moving it without shrinking `chart_width` would
        # have satisfied the words and failed the ask, so the gutter goes with it.
        # ⚠️ `text-anchor='end'` RATHER THAN SUBTRACTING A MEASURED WIDTH. The glyphs are
        # monospace at a known pitch, so both would work — but an anchor cannot drift out of
        # step with `_CURVE_LABEL_CHAR_PX` the way a second width calculation could.
        # 🚨 A167 (cfdb-main-R-1312). THE PERCENTAGE POPS; THE ABBREVIATION DOES NOT.
        #
        # > **MARC, v06:** *"Increase the font of the final win % and make it blue to help it
        # > pop out."*
        #
        # ⚠️ **HE SAID "the final win %", NOT "the label"** — so the team abbreviation keeps the
        # size and the muted opacity it has, and only the number grows and takes the colour.
        # **Two `tspan`s in one `<text>`, which keeps the whole thing anchored at one x** and
        # therefore keeps A165's `text-anchor='end'` geometry intact.
        #
        # 🚨 **"BLUE" IS A TOKEN, NOT A HEX.** `var(--cfdb-link)` is the site's link colour and
        # it is theme-aware; a literal like `#1f77b4` is a blue that is wrong on one of the two
        # pages, which is the class of mistake A165 measured on the poll ladder.
        #
        # ⚠️ **AND `chart_width` MUST NOT START BUYING WIDTH AGAIN.** The label is anchored at
        # its RIGHT edge and grows LEFTWARD into the plot, so a bigger number costs the chart
        # nothing — A165 took the regulation chart 224px -> 182px as Marc's *"tighten up the
        # horizontal space"* and this must not give it back.
        #
        # ⚠️ **THE `cut` BRANCH IS NOT A VALUE AND IS NOT STYLED AS ONE.** It is the word "cut",
        # meaning the feed stopped — colouring it like a win probability would dress an absence
        # as a measurement.
        abbreviation, _, percentage = label.rpartition(" ")
        if is_cut or not percentage.endswith("%"):
            # ⚠️ NO `tspan` HERE. The cut branch is one run of plain text at the base size, and
            # wrapping it changes markup that other assertions read for no visual gain.
            body = label
        else:
            body = ((f"<tspan>{abbreviation} </tspan>" if abbreviation else "")
                    # 📊 `fill='var(...)'` ON A PRESENTATION ATTRIBUTE WORKS, AND THAT WAS
                    # CHECKED RATHER THAN ASSUMED BOTH WAYS (cfdb-main-R-1313). Measured in
                    # Chromium with the sheets injected as the app injects them:
                    # `fill='var(--cfdb-link)'` and `style='fill:var(--cfdb-link)'` BOTH resolve
                    # to `rgb(31,111,235)` on light and `rgb(88,166,255)` on dark. The attribute
                    # form is kept because it is what every other mark in this SVG uses.
                    #
                    # 🚨 AND A MEASUREMENT SAID OTHERWISE FIRST, BECAUSE THE INSTRUMENT WAS
                    # WRONG. A render harness wrapped `theme.CSS` and `theme.TABLE_CSS` in an
                    # extra `<style>` — **both strings already carry their own** — which broke
                    # the `:root` block where `--cfdb-link` is declared, so the token resolved
                    # to nothing and the percentage inherited `currentColor`. **The page was
                    # correct and the ruler was bent** (§2.4: say what the command answered).
                    + f"<tspan font-size='{_CURVE_FINAL_SIZE}' fill='var(--cfdb-link)' "
                      f"font-weight='700'>{percentage}</tspan>")
        parts.append(f"<text x='{last_x - _CURVE_LABEL_OFFSET:.1f}' y='{label_y:.1f}' "
                     f"text-anchor='end' font-size='9' font-family='{_CURVE_LABEL_FONT}' "
                     f"fill='currentColor' opacity='.75'>{body}</text>")

    return (f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' "
            f"role='img' aria-label='{described}' "
            f"style='display:block'>{''.join(parts)}</svg>")
