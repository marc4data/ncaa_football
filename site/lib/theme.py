"""One stylesheet, injected once. Chrome only — nothing here encodes a value.

Every colour is a neutral or a semantic state colour. Team colours arrive per-row from
dim_team and appear only as accent rules (AC-G.25), so there is deliberately no team colour
anywhere in this file.
"""
import streamlit as st

CSS = """
<style>
.cfdb-state { border-radius:8px; padding:1rem 1.1rem; margin:.4rem 0 .8rem;
  border:1px solid var(--cfdb-border,#d7dae0); background:var(--cfdb-bg,#fafbfc); }
.cfdb-state-title { font-weight:600; margin-bottom:.25rem; }
.cfdb-state-body { opacity:.85; font-size:.92rem; }
.cfdb-state-object { margin-top:.5rem; font-size:.88rem; }
.cfdb-state-note { margin-top:.35rem; font-size:.82rem; opacity:.7; }
.cfdb-empty    { border-left:4px solid #9aa3ae; }
.cfdb-degraded { border-left:4px solid #b7791f; }
.cfdb-error    { border-left:4px solid #c53030; }
.cfdb-state code { background:rgba(0,0,0,.06); padding:.08rem .35rem; border-radius:4px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }

/* Skeleton at the loaded layout's dimensions, so the page never jumps (AC-G.8). */
.cfdb-skel { display:flex; flex-direction:column; gap:.55rem; }
.cfdb-skel-row { height:1.55rem; border-radius:5px;
  background:linear-gradient(90deg,#eceef1 25%,#f5f6f8 37%,#eceef1 63%);
  background-size:400% 100%; animation:cfdb-shimmer 1.3s ease-in-out infinite; }
@keyframes cfdb-shimmer { 0%{background-position:100% 50%} 100%{background-position:0 50%} }

/* Fixed width so "Cover" and "DNC" occupy the same box (AC-G.20). Glyph carries the
   meaning; color is the second signal, so it survives grayscale (AC-G.21/22). */
.cfdb-chip { display:inline-flex; align-items:center; justify-content:center; gap:.3rem;
  min-width:6.2rem; padding:.14rem .5rem; border-radius:999px; font-size:.8rem;
  font-weight:600; border:1px solid currentColor; }
.cfdb-chip-glyph { font-weight:700; }
.cfdb-chip-y { color:#1b7f4b; background:rgba(27,127,75,.10); }
.cfdb-chip-n { color:#b02a37; background:rgba(176,42,55,.10); }
.cfdb-chip-w { color:#5b6470; background:rgba(91,100,112,.10); }
.cfdb-chip-p { color:#1f6feb; background:rgba(31,111,235,.10); }
.cfdb-chip-r { color:#b7791f; background:rgba(183,121,31,.12); }

/* Numeric columns compare vertically only if they are monospace and right-aligned. */
.cfdb-num { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; text-align:right;
  font-variant-numeric:tabular-nums; }

.cfdb-logo { border-radius:4px; object-fit:contain; vertical-align:middle; }
.cfdb-monogram { display:inline-block; text-align:center; border-radius:4px; color:#fff;
  font-size:.72rem; font-weight:700; vertical-align:middle; }
.cfdb-hint { opacity:.55; margin-left:.25rem; cursor:help; }
/* THE WEEK BAND AND ITS DISTRIBUTIONS.
   One row, and it must stay one row: prompt 036 spent a round removing eleven rows from above
   the first card, and a band that wraps hands them straight back. The thumbnails are
   `flex-shrink` and the label is not, so a narrow viewport squeezes the pictures rather than
   pushing them onto a second line. */
.cfdb-weekband { display:flex; align-items:center; gap:1rem; flex-wrap:nowrap;
    margin:.2rem 0 .5rem; padding:.35rem 0; border-top:1px solid rgba(127,127,127,.28);
    border-bottom:1px solid rgba(127,127,127,.28); overflow:hidden; }
.cfdb-weekband-title { font-weight:700; font-size:.95rem; white-space:nowrap;
    letter-spacing:.02em; flex:0 0 auto; }
.cfdb-weekband-strip { display:flex; gap:1.1rem; align-items:center; min-width:0;
    flex:1 1 auto; justify-content:flex-end; }

.cfdb-dist { display:inline-flex; align-items:center; gap:.35rem; min-width:0;
    flex:0 1 auto; }
.cfdb-dist-label { font-size:.66rem; letter-spacing:.06em; text-transform:uppercase;
    opacity:.62; white-space:nowrap; }
.cfdb-dist-median { font-size:.78rem; font-variant-numeric:tabular-nums; opacity:.9;
    white-space:nowrap; }
/* The SVG carries the color; the bars are drawn in currentColor so the whole thing themes
   for free and needs no light/dark variant. */
.cfdb-dist-svg { display:block; color:inherit; }
/* An absent week reserves the SAME WIDTH as a present one. R-141: an element that appears
   only when populated shifts everything beside it the moment a week is half-priced. */
.cfdb-dist-empty { opacity:.45; }
.cfdb-dist-none { font-size:.9rem; opacity:.6; }

/* R-477. The offense/defense scatter. Same approach as the distribution chart above: the
   marks are currentColor so the whole thing themes for free and needs no light/dark variant,
   which is also why there is no palette here to validate. One series, one hue, no legend —
   the chart standard's §7. Nothing encodes a judgement: no color scale, no threshold line,
   no quadrant shading. */
/* 🚨 A190 (cfdb-main-R-1938). `position:relative` AND THE SVG FILLING ITS BOX ARE WHAT MAKE
   THE HOVER LAYER LINE UP. Each hotspot is placed at `cx/viewBox-width%`, so the percentages
   only land on the marks while the SVG is `width:100%; height:auto` with its viewBox aspect
   ratio and the layer is `inset:0` on this box. Change either and every tooltip drifts off
   its point — silently, because nothing throws. `test_the_scatter_overlay_can_line_up_with
   _the_marks` holds both halves. */
.cfdb-scatter { margin:.2rem 0 .1rem; position:relative; }
.cfdb-scatter svg { display:block; width:100%; height:auto; color:inherit; }

/* ── A190: the hover layer ─────────────────────────────────────────────────────────────────
   ⚠️ CSS-ONLY, AND NOT BY CHOICE: Streamlit's `unsafe_allow_html` strips `<script>`, so there
   is no JS to position anything with. Each hotspot owns its tooltip and shows it on `:hover`
   and `:focus-within` — the second is what makes it work on a tap and from a keyboard, which
   `:hover` alone cannot do. */
.cfdb-sc-layer { position:absolute; inset:0; }
.cfdb-sc-hot { position:absolute; width:18px; height:18px; margin:-9px 0 0 -9px;
               border-radius:50%; cursor:pointer; outline:none; }
.cfdb-sc-hot:focus-visible { outline:2px solid var(--cfdb-link); outline-offset:1px; }
.cfdb-sc-tip { position:absolute; z-index:5; visibility:hidden; opacity:0;
               transition:opacity .08s linear;
               min-width:12rem; max-width:17rem; padding:.45rem .55rem;
               background:var(--cfdb-sticky-bg); color:CanvasText;
               border:1px solid var(--cfdb-edge); border-radius:4px;
               box-shadow:0 2px 10px rgba(0,0,0,.18);
               font-size:.72rem; line-height:1.25; text-align:left;
               pointer-events:none; }
.cfdb-sc-hot:hover .cfdb-sc-tip,
.cfdb-sc-hot:focus .cfdb-sc-tip,
.cfdb-sc-hot:focus-within .cfdb-sc-tip { visibility:visible; opacity:1; }
/* The flip. `data-side`/`data-vert` are computed in Python from the point's own position,
   because CSS cannot ask where its element sits — see `_scatter_hotspot`. */
.cfdb-sc-tip[data-side='right'] { left:16px; }
.cfdb-sc-tip[data-side='left']  { right:16px; }
.cfdb-sc-tip[data-vert='down']  { bottom:6px; }
.cfdb-sc-tip[data-vert='up']    { top:6px; }
.cfdb-sc-head { display:flex; align-items:center; gap:.3rem; flex-wrap:wrap;
                margin-bottom:.25rem; }
.cfdb-sc-logo { width:18px; height:18px; object-fit:contain; flex:0 0 auto; }
.cfdb-sc-team { font-weight:700; }
.cfdb-sc-rank { font-weight:700; opacity:.75; font-size:.68rem; }
.cfdb-sc-unranked { opacity:.55; font-size:.66rem; font-style:italic; }
.cfdb-sc-record { opacity:.6; font-size:.68rem; }
.cfdb-sc-stat { display:block; }
.cfdb-sc-stat i { font-style:normal; opacity:.6; font-size:.66rem; }
.cfdb-sc-pop { opacity:.5; font-size:.62rem; margin-top:.15rem; }
.cfdb-sc-vs { margin-top:.3rem; padding-top:.25rem; font-size:.68rem;
              border-top:1px solid var(--cfdb-rule-soft);
              display:flex; align-items:center; gap:.25rem; flex-wrap:wrap; }
/* A190: the ring marking a team the distance table lists. */
/* A190's ring around a ranked mark. A203 replaced it with the team's logo
   (Marc: "instead of putting the second circle around the mark"), so nothing
   emits this class any more. Kept out of the stylesheet rather than kept. */

/* ── A190: the distance table beside the chart ────────────────────────────────────────────
   Six columns in ~18% of the row, so the team name is the only flexible one and everything
   else is sized to its content. */
/* 🚨 A208 (cfdb-main-R-2261). A190's STACKING CLAIM STOOD HERE AND IS FALSE — it was
   measured false by A203 (see `.cfdb-far` below), and the paragraph outlived the rule it
   described: the block it sat above is the SLATE's, and nothing here has a `min-width` at
   all. Streamlit's columns do NOT wrap out of a two-column row whose bases sum to 100%; a
   `min-width` larger than the column overflows and is clipped. The remedy is the scroller,
   which is now `.cfdb-scroll`'s job for every wide table on the site. */
/* ── A198: the SLATE — one row per game, time across the x-axis ───────────────────────────
   ⚠️ `currentColor` THROUGHOUT, like `lib/distribution.py` and the scatter: the drawing takes
   the page's own ink and is therefore correct in both themes with no second palette to keep
   in step. The one accent is the Top 25 bar, which is the same `--cfdb-link` the page uses
   for a link — a rank is the strongest signal on this chart and it earns one hue. */
/* A207's container, A208's class: the SLATE carries `.cfdb-scrollbox` so its note can ask
   how wide THIS SECTION is. The viewport is the wrong question — the sidebar's width changes
   the answer. The note, the query and the boundary are all shared now; see `.cfdb-scroll`. */
.cfdb-slate { margin:.3rem 0 .2rem; }
.cfdb-slate svg { display:block; width:100%; height:auto; color:inherit; }
/* A201. The SLATE is a schedule table whose last column holds the graph. The left cells are
   Schedule's own, so they inherit `.cfdb-table`; only the graph column is new. */
/* 🚨 A MINIMUM, SO THE GRAPH CANNOT BE SQUEEZED TO NOTHING. 📊 A201 measured it: with the
   fixed columns at 642px and the scroll box 640px at 1100, the graph column got 0px and all
   twelve hour labels piled up outside it.
   ⚠️ A209 CORRECTION (cfdb-main-R-2454): the numbers in this paragraph went stale the day
   A204 added `Wx` and `O/U`. The fixed columns are **762px**, not 642, and 940 leaves the
   axis **178px**, not the ~300 this used to claim. 📊 Re-measured: the widest hour label is
   16.47px and adjacent labels sit 0.13227 of the axis apart, so 178 is above the 154.8 the
   labels need — narrow, and not piled up.
   ✅ And 642 is live again as `_SLATE_NARROW_FIXED_PX`: below 940 the SLATE puts `O/U` and
   `Wx` away and the table's minimum drops to 820, which is where A201's arithmetic came from
   in the first place. `views/today.py` owns all four numbers. */
/* A208: the scrollbar styling and the note moved to `.cfdb-scroll`, which every wide table
   on the site already uses. Nothing SLATE-specific is left here; `_SLATE_MIN_PX` in
   `views/today.py` is the one place 940 is written, and the table carries it inline. */
.cfdb-slate-table { table-layout:fixed; width:100%; }
.cfdb-slate-table td, .cfdb-slate-table th { padding-top:.2rem; padding-bottom:.2rem; }
.cfdb-slate-table .cfdb-slate-cell { padding-left:.5rem; padding-right:.2rem; }
.cfdb-slate-table .cfdb-slate-tv { white-space:nowrap; }
/* A205. The SLATE's team names link to the Teams page, the way Schedule's do. The RECORD is
   outside the anchor (R-129) — styling cannot remove a pointer cursor, and dead text under
   one is worse than either state. */
.cfdb-slate-teamlink { color:var(--cfdb-link); text-decoration:none; }
.cfdb-slate-teamlink:hover .cfdb-team { text-decoration:underline; }
.cfdb-slate-table .cfdb-slate-why { padding-left:.2rem; padding-right:.2rem; }
/* 🚨 SCOPED WITH THE PARENT, BECAUSE `.cfdb-slate svg` ABOVE OUT-SPECIFIES A BARE CLASS.
   A200 hit this exact rule with the key swatch and wrote it down; the first build of A201 hit
   it again with the plot, whose `height:auto` against a stretched viewBox drew a 26-unit row
   several hundred pixels tall. Specificity here is 0-2-0 against that rule's 0-1-1. */
/* 🚨 A204. THE BAR IS AN HTML BOX, NOT AN SVG RECT, and that is what lets the kickoff label
   live inside it. A201 stretched each row's SVG with preserveAspectRatio='none', which
   distorts every glyph it contains — the reason A201's own hour labels had to leave the SVG.
   A percent-positioned box needs no stretch at all. */
.cfdb-slate-track { position:relative; height:22px; }
.cfdb-slate .cfdb-slate-bar { position:absolute; top:3px; height:16px; min-width:2px;
    border-radius:3px; box-sizing:border-box; display:flex; align-items:center;
    overflow:hidden; background:currentColor; border:1px solid currentColor; }
/* The fills, as opacities of the row's own color so both themes track it. */
.cfdb-slate .cfdb-slate-bar { background-color:color-mix(in srgb, currentColor 26%, transparent);
    border-color:color-mix(in srgb, currentColor 46%, transparent); }
.cfdb-slate .cfdb-slate-bar-top {
    background-color:color-mix(in srgb, var(--cfdb-link) 52%, transparent);
    border-color:color-mix(in srgb, var(--cfdb-link) 78%, transparent); }
/* 📊 30%, NOT 40%, AND THE NUMBER IS MEASURED. At 40% the kickoff label read 4.44:1 against
   this fill in dark mode — under the 4.5 that small text needs — because dark mode puts
   near-white ink on a light-gray fill. Darkening the fill is what buys the contrast back;
   lightening the ink cannot, it is already near-white. Light mode was 4.83 and is unharmed. */
.cfdb-slate .cfdb-slate-bar-und {
    background-color:color-mix(in srgb, currentColor 30%, transparent);
    border-color:color-mix(in srgb, currentColor 58%, transparent); }
.cfdb-slate .cfdb-slate-bar-added {
    background-color:color-mix(in srgb, var(--cfdb-link) 20%, transparent);
    border-color:color-mix(in srgb, var(--cfdb-link) 46%, transparent); }
/* PART 2: the kickoff, inside the bar and flush left. It clips rather than overflowing, so a
   bar too narrow to hold it loses the label instead of spilling into the column before it. */
.cfdb-slate-clock { font-size:.6rem; line-height:1; padding-left:3px; white-space:nowrap;
    color:var(--cfdb-text); opacity:.92; }
/* 🚨 PART 3: ONE SET OF LINES BEHIND THE WHOLE DAY. Per-row lines cannot be continuous —
   every row adds its own padding and border, so the line restarts at each one, which is the
   "weird look" Marc named. This layer sits behind the table, inset by the fixed columns. */
.cfdb-slate-block { position:relative; }
.cfdb-slate-grid { position:absolute; top:0; right:0; bottom:0; pointer-events:none; }
.cfdb-slate-grid i { position:absolute; top:1.35rem; bottom:0; width:1px;
    background:currentColor; opacity:.14; }
.cfdb-slate-block .cfdb-slate-table { position:relative; background:transparent; }
.cfdb-slate-block .cfdb-slate-table td, .cfdb-slate-block .cfdb-slate-table th {
    background:transparent; }
.cfdb-slate .cfdb-slate-slots { display:inline-block; width:auto; height:16px; }
/* The axis is HTML: percent-positioned spans, so the glyphs are not stretched by the plot's
   `preserveAspectRatio='none'`. */
.cfdb-slate-axis { position:relative; height:14px; }
.cfdb-slate-axis .cfdb-slate-hour { position:absolute; transform:translateX(-50%);
                                    font-size:.62rem; opacity:.55; white-space:nowrap; }
.cfdb-slate-axis .cfdb-slate-hour-first,
.cfdb-slate-axis .cfdb-slate-hour-last { transform:none; }
.cfdb-slate-day { font-size:.72rem; font-weight:700; letter-spacing:.04em;
                  text-transform:uppercase; opacity:.65; margin:.5rem 0 .1rem; }
.cfdb-slate-grid { stroke:currentColor; stroke-opacity:.14; stroke-width:1; }
.cfdb-slate-hour { fill:currentColor; fill-opacity:.5; font-size:9.5px; }
.cfdb-slate-label { fill:currentColor; fill-opacity:.85; font-size:11px; }
.cfdb-slate-net { fill:currentColor; fill-opacity:.55; font-size:10px; }
/* A201, Marc: "Give the bars a thin medium graph outline to make them pop a bit." The
   stroke is `currentColor` at a middling opacity, so it reads in both themes without being a
   second color to keep in step. `vector-effect` on the rect keeps it one pixel — the SVG is
   stretched horizontally, so a scaled stroke would draw a fat left edge and a hairline top. */
.cfdb-slate-bar { fill:currentColor; fill-opacity:.28;
                  stroke:currentColor; stroke-opacity:.45; stroke-width:1; }
.cfdb-slate-bar-top { fill:var(--cfdb-link); fill-opacity:.55; }
/* A game whose kickoff is not announced gets NO bar — see `today._slate_rows`. It is named
   here instead, because a bar at a placeholder time is a fabricated slot on a run sheet. */
.cfdb-slate-bar-und { fill:currentColor; fill-opacity:.42; }
.cfdb-slate-bar-added { fill:var(--cfdb-link); fill-opacity:.22; }
/* A200. The reason marks and their key. SHAPES, not hues: this chart prints, and a key
   keyed on color alone is a blank key on a laser printer. */
.cfdb-slate-logo { opacity:.95; }
.cfdb-slate-mark { fill:currentColor; fill-opacity:.75; }
.cfdb-slate-mark-line { fill:none; stroke:currentColor; stroke-opacity:.75; stroke-width:1.8;
                        stroke-linecap:round; }
.cfdb-slate-key { display:flex; flex-wrap:wrap; gap:.15rem 1rem; align-items:center;
                  font-size:.7rem; opacity:.75; margin:.1rem 0 .35rem; }
/* 🚨 HIGHER SPECIFICITY THAN `.cfdb-slate svg { width:100% }`, WHICH THIS SITS INSIDE.
   Without this the 12x12 key swatch stretches to the full chart width — one gray circle
   980px across, found in a render and invisible in the markup. */
.cfdb-slate .cfdb-slate-key-mark { flex:0 0 auto; width:12px; height:12px;
                                   display:inline-block; margin-right:.25rem;
                                   vertical-align:-1px; }
.cfdb-slate-key-text { margin-right:.4rem; }
.cfdb-slate-tba { font-size:.72rem; opacity:.7; margin:.35rem 0 .1rem; }

/* ── A196: the "why is this game here" tag on Looking Forward ─────────────────────────────
   ⚠️ IT READS THE PUBLISHED FLAGS AND DECIDES NOTHING (see `today._reasons`), and
   BOTH tags can appear on one game — a Top 25 matchup that is also an undefeated side at a
   short line. Showing only the first would make the second rule look narrower than it is. */
.cfdb-why { display:inline-flex; flex-wrap:wrap; gap:.25rem; }
.cfdb-why-tag { font-size:.62rem; line-height:1.4; padding:.05rem .3rem; white-space:nowrap;
                border:1px solid var(--cfdb-edge); border-radius:3px; opacity:.8; }

/* A203. THE TABLE IS A TABLE NOW, AND THE TYPE IS THE SITE'S NORMAL TABLE SIZE.
   > MARC: "The table needs to be bigger... Font needs to be bigger" and "Create columns for
   > the Gained and Allowed so the values are vertically aligned".
   A190 used .72rem on a two-line grid because six facts did not fit on one line at 18% of the
   row; Marc has since allowed more width, so this is .9rem — `.cfdb-table`'s own size — on one
   line per team. ⚠️ A208: the sentence that stood here said the min-width makes the column
   drop below the chart — A190's claim, which the next comment measures FALSE. It squeezes;
   the scroller is what saves it. */
/* 🚨 A203 MEASURED A190's `min-width` CLAIM AND IT IS FALSE.
   A190's comment says the min-width makes this column "drop to its own full-width line"
   because Streamlit's row is `flex-wrap:wrap`. 📊 It does not: the two columns' bases sum to
   100%, so nothing wraps, and a min-width larger than the column simply OVERFLOWS and is
   clipped. Measured at 1100 the column is 210px, the table wanted 304px, and its right edge
   sat **94px past the block** — the Allowed column was off-screen with no way to reach it.
   ✅ So the table SCROLLS inside its own column. `min-width:0` lets the column shrink; the
   minimum on the TABLE (`_FAR_MIN_PX`, inline from `views/today.py`) keeps the columns their
   measured size and hands the overflow to the scroller.
   ⚠️ A208 CORRECTION: this sentence used to end by naming Schedule's list and A201's SLATE as
   two tables that already scroll at 1100. 📊 Schedule's list does not — `views/schedule.py`
   calls `table.render` without `scroll=True` and emits no wrapper at all. FOUR wrappers exist
   site-wide and they are enumerated at `.cfdb-scroll`. */
.cfdb-far { font-size:.9rem; min-width:0; }
.cfdb-far-head { font-weight:700; font-size:.78rem; letter-spacing:.04em;
    text-transform:uppercase; opacity:.7; margin-bottom:.3rem; }
.cfdb-far-table { width:100%; border-collapse:collapse;
    table-layout:fixed;
    font-variant-numeric:tabular-nums; }
.cfdb-far-table th { font-size:.68rem; font-weight:700; letter-spacing:.03em;
    text-transform:uppercase; opacity:.55; text-align:left; padding:0 .25rem .2rem 0;
    border-bottom:1px solid currentColor; border-color:color-mix(in srgb, currentColor 18%,
    transparent); }
.cfdb-far-table td { padding:.16rem .25rem .16rem 0; vertical-align:middle; }
.cfdb-far-table tbody tr:hover td { background:color-mix(in srgb, currentColor 6%,
    transparent); }
.cfdb-far-numhead { text-align:right; }
.cfdb-far-rank { width:1.6rem; font-weight:700; opacity:.45; text-align:right;
    padding-right:.4rem !important; }
.cfdb-far-team { min-width:0; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.cfdb-far-logo { width:18px; height:18px; object-fit:contain; vertical-align:middle;
    display:inline-block; margin-right:.3rem; }
.cfdb-far-name { vertical-align:middle; }
.cfdb-far-link { color:var(--cfdb-link); text-decoration:none; }
.cfdb-far-link:hover { text-decoration:underline; }
.cfdb-far-rec { opacity:.5; font-weight:400; margin-left:.3rem; font-size:.78rem;
    vertical-align:middle; }
.cfdb-far-num { width:4.6rem; }
/* A203. A spark that sits BESIDE its number rather than under it — see `_far_spark` for the
   66px measurement that rules out the shared `.cfdb-spark` overlay in this column. */
.cfdb-far-spark { display:flex; align-items:center; gap:.3rem; justify-content:flex-end; }
.cfdb-far-spark-track { flex:1 1 auto; min-width:0; height:.72em; border-radius:2px;
    background:color-mix(in srgb, currentColor 10%, transparent); }
.cfdb-far-spark-bar { display:block; height:100%; border-radius:2px;
    background:color-mix(in srgb, currentColor 42%, transparent); }
.cfdb-far-spark-value { flex:0 0 auto; text-align:right; }
.cfdb-far-foot { opacity:.55; font-size:.68rem; margin-top:.35rem; line-height:1.3; }
.cfdb-far-none { opacity:.6; font-size:.78rem; padding:.4rem 0; }
/* A178 (cfdb-main-R-1853). "Mute (lighter by 50%) down the current gridlines" — .14 -> .07,
   which is his 50% exactly, and with the ladder now at 100-yard steps there are half as many
   of them as well. */
.cfdb-sc-grid { stroke:currentColor; stroke-opacity:.07; stroke-width:1; }
/* The median lines are the ones meant to be READ, so they are the only strokes on this chart
   that are not hairlines. Dashed rather than solid: a solid rule at this weight reads as an
   axis, and the axes are hairlines — the reader would have the hierarchy upside down. */
.cfdb-sc-median { stroke:currentColor; stroke-opacity:.45; stroke-width:1.5;
                  stroke-dasharray:5 3; }
.cfdb-sc-median-label { fill:currentColor; fill-opacity:.55; font-size:9.5px;
                        letter-spacing:.02em; }
/* A176. UNFILLED, IN THE TEAM'S OWN COLOR, AND THIS RULE IS WHY IT NEEDED A RASTER.
   > MARC, v09: "Make these unfilled circles. Color by Team color"
   The mark carries `fill='none' stroke='<the team color>'` as PRESENTATION ATTRIBUTES, and a
   CSS declaration BEATS a presentation attribute — so `fill:currentColor` here drew every
   circle filled with the page's text color while the SVG source said `fill='none'` and the
   test asserting that source PASSED. R-855's lesson exactly: the picture caught what reading
   the code could not.
   (American spelling throughout: this string IS `theme.CSS` and ships to the browser, so the
   spelling guard reads it as user-facing — it caught this comment's first draft.)
   The old rule's reason still holds and is now served by the stroke instead: 138 marks on one
   chart WILL overlap, and a ring at .85 lets an overlapped team stay visible through it where
   a solid disc hid it. */
.cfdb-sc-pt { fill:none; stroke-opacity:.85; }
.cfdb-sc-tick { fill:currentColor; fill-opacity:.55; font-size:10px;
    font-variant-numeric:tabular-nums; }
/* A203. The axis NAME is the big word; the direction line stays small beneath it. Marc:
   "Vertical Axis Label Title should have a big Offense, the better, more yards is a subtitle,
   can be smaller." */
.cfdb-sc-axis { fill:currentColor; fill-opacity:.6; font-size:10px; }
.cfdb-sc-axis-name { fill:currentColor; fill-opacity:.85; font-size:15px; font-weight:700;
    letter-spacing:.02em; }
/* The logo that replaces a ranked team's mark. A203, Marc: "replace the initial circle with
   the logo for the top 10". */
.cfdb-sc-mark-logo { opacity:.95; }
/* The good corner, named on the plot itself — a reader scans the shape before the words. */
.cfdb-sc-corner { fill:currentColor; fill-opacity:.5; font-size:10px;
    letter-spacing:.02em; }

.cfdb-dist-panel { border:1px solid rgba(127,127,127,.25); border-radius:6px;
    padding:.6rem .75rem; margin:.4rem 0; }
.cfdb-dist-head { display:flex; align-items:baseline; gap:.6rem; margin-bottom:.3rem; }
.cfdb-dist-sub { font-size:.72rem; opacity:.6;
    font-family:ui-monospace,Menlo,monospace; }
.cfdb-dist-body { display:flex; gap:.9rem; align-items:flex-start; }
.cfdb-dist-body .cfdb-dist-svg { flex:1 1 auto; min-width:0; }
/* The stats are a TABLE, not a caption — label left, value right, monospace. That is what
   makes them scannable and it is what plot_distribution does. */
.cfdb-dist-stats { flex:0 0 auto; font-family:ui-monospace,Menlo,monospace;
    font-size:.72rem; min-width:6.5rem; }
.cfdb-dist-stat { display:flex; justify-content:space-between; gap:.8rem; opacity:.85; }
.cfdb-dist-stat b { font-variant-numeric:tabular-nums; }

.cfdb-footer { margin-top:2.5rem; padding-top:.8rem; border-top:1px solid #e3e6ea;
  font-size:.82rem; opacity:.75; }
.cfdb-readiness { font-size:.8rem; opacity:.7; font-family:ui-monospace,Menlo,monospace; }

/* R-144. THE EMPTY BAND ABOVE THE TITLE, AND THE NUMBER IS MEASURED NOT ASSUMED.
   Streamlit reserves `padding-top:6rem` on the main container for `stHeader`, a FIXED overlay
   that this site puts nothing in. Pad less than the header's rendered height and the title
   slides under the hamburger — invisible standing still, obvious the moment content scrolls.
   MEASURED IN THE DEPLOYED CONTAINER, not locally, because the header renders differently with
   and without the Deploy button and `--server.headless` changes that:
       stHeader height   60px   (position:absolute, top 0; hamburger bottom at 45px)
       default padding   96px
   4rem = 64px clears the header by 4px and returns 32px of the band. Marc kept stHeader, so
   the theme switcher and Rerun stay reachable. */
[data-testid="stMainBlockContainer"], .block-container {
    padding-top:4rem !important; }
/* R-163. R-144 FIXED THE CONTAINER AND MARC STILL SAW THE BAND, BECAUSE IT WAS A DIFFERENT
   ELEMENT. Streamlit's own `h1` carries padding of its own that nothing had touched.
   MEASURED IN THE DEPLOYED CONTAINER, on the pinned version, per R-151:
       h1   padding-top 20px, padding-bottom 16px, box 89px tall for one line of text
   The title needs separation from the status beside it, not 36px of it. 0/8 keeps the
   descender clear and returns 28px. */
.cfdb-app h1, [data-testid="stMainBlockContainer"] h1 {
    padding-top:0 !important; padding-bottom:.5rem !important; }
/* R-547. THIS BLOCK USED TO BE `@media (prefers-color-scheme: dark)`, AND MARC SAW WHAT
   THAT COSTS: a dark card sitting in a light page. He was in Light theme, the Empty state
   under "Offense and defense, per game" rendered dark, and he guessed it was because of the
   hour. It is not — a Streamlit app does not know the time. His OPERATING SYSTEM is in dark
   mode, `prefers-color-scheme` answers the operating system, and the app theme never
   entered into it.

   ⚠️ THIS FILE ALREADY DIAGNOSED THIS EXACT FAILURE AND FIXED IT SOMEWHERE ELSE. See
   TABLE_CSS below, which says it in as many words: "A reader on a dark system who switches
   the app to Light gets a light page painted with dark cells — which is what happened."
   That repair converted the frozen-column tokens to `Canvas`/`CanvasText` and left these
   three declarations behind, still asking the operating system. The media query is deleted
   rather than corrected, because there is nothing to correct: the question it asks is the
   wrong question, and leaving it in place for the two rules Marc had not yet noticed would
   have banked the same bug twice.

   `Canvas` and `CanvasText` follow the `color-scheme` property Streamlit sets from the
   ACTIVE theme, so these track the switch in the same frame the rest of the page does, with
   no Python in the loop and nothing to go stale. `color-mix` derives the rest from the same
   two so a card is a tint of the page it sits on in either theme, rather than two more
   hardcoded colors to keep in step. */
.cfdb-state {
  --cfdb-border: color-mix(in srgb, CanvasText 18%, Canvas);
  --cfdb-bg:     color-mix(in srgb, CanvasText 3%,  Canvas);
}
.cfdb-skel-row {
  background:linear-gradient(90deg,
    color-mix(in srgb, CanvasText 8%,  Canvas) 25%,
    color-mix(in srgb, CanvasText 4%,  Canvas) 37%,
    color-mix(in srgb, CanvasText 8%,  Canvas) 63%);
  background-size:400% 100%; }
.cfdb-footer { border-top-color: color-mix(in srgb, CanvasText 18%, Canvas); }
</style>
"""


# NO PYTHON THEME RESOLUTION ANY MORE, AND THE REASON IS WORTH KEEPING.
#
# `st.context.theme` reports the ACTIVE theme, which is the right question — and it answers
# it one rerun late. Streamlit repaints the moment the reader flips the switch; Python only
# hears about it on the next script run, so the tokens lagged and some frozen cells kept the
# previous theme's colour until a tab change forced another pass. That is exactly what Marc
# saw: "The switch between Light and Dark misses some of the Frozen columns."
#
# The tokens are built from `Canvas` and `CanvasText` instead, which follow the `color-scheme`
# property Streamlit sets from that same active theme — live, in the same frame, with nothing
# to synchronise. See TABLE_CSS.

# ── THE THEME A CHART IS BEING DRAWN INTO ────────────────────────────────────────────────
#
# 🚨 A165 PROMOTED THIS OUT OF `matchup.py` (cfdb-main-R-1303). B136 built it for the drives
# panel; the poll chart needs the identical answer, and **two copies of one question is the
# drift this file opens by warning about (§4.3).** `site/lib/` is session A's, which is why the
# promotion happens here rather than the second caller importing from a view.
#
# ⚠️ **IT IS A MOVE, NOT A COPY.** `matchup.py` now calls this and defines nothing of its own —
# asserted by count in `test_exactly_one_producer_answers_which_theme_the_viewer_is_in`, because
# "I removed the old one" is not a measurement.
#
# ## 🚨 HOW A VEGA SPEC LEARNS WHICH THEME IT IS IN — THE QUESTION B135 STOPPED ON
#
# ❌ **NOT `light-dark()`. B135 tested it inside a Vega mark and Vega rejected the string,
# falling back to `#ddd` in BOTH themes.** The page's CSS mechanism is unavailable in a chart,
# because the colour is baked into the spec before the browser ever sees it.
#
# ✅ **THE ANSWER IS `st.context.theme.type`, WHICH IS SERVER-SIDE AND PER SESSION.** Streamlit
# 1.63 exposes the theme the VIEWER is actually in, inferred from the app's background colour —
# so the spec can be built with the right colour already in it.
#
# ⚠️ **AND STREAMLIT'S OWN DOCSTRING WARNS THAT IT "MAY BE INCORRECT … WHEN THE APP IS FIRST
# LOADED WITHIN A SESSION", WHICH WOULD HAVE BEEN FATAL HERE** — a reader reaches this panel by
# URL, so the first load IS the common case. 📊 **SO IT WAS MEASURED RATHER THAN TRUSTED: a probe
# app was run under a real Streamlit server and loaded in Chromium in a FRESH browser context
# per scheme, which is a new session, so `run=1` is genuinely the first load:**
#
#     browser color-scheme: light   run=1 type='light'   page background rgb(255,255,255)
#     browser color-scheme: dark    run=1 type='dark'    page background rgb(14,17,23)
#
# ✅ **Correct on the first script run in both schemes.** ⚠️ **The caveat is real for a theme
# CHANGED mid-session, which is why the fallback below is what it is.**
#
# 🚨 **THE FALLBACK IS *TODAY'S BEHAVIOUR*, DELIBERATELY, SO THIS CANNOT REGRESS LIGHT.** Where
# the theme is unknown — no script-run context, an older Streamlit, a stub that does not provide
# it — this reads as LIGHT, which is exactly what shipped before. **A fix that traded one theme
# for the other would not be a fix, and the only way to be sure is for the unknown case to land
# on the variant that is already correct 100% of the time on the light page.**
def viewer_is_dark() -> bool:
    """Whether the viewer is in dark mode. **THE ONE PLACE THE SITE ASKS.**

    ⚠️ **EVERY `getattr` HERE IS A REAL CASE, NOT DEFENSIVE PROGRAMMING.** `st.context` arrived
    in a recent Streamlit; `theme.type` is documented as `None` when the runtime has no context
    info; and a test stub may model neither. **Each of those falls to light, which is what this
    panel already did — so an unknown theme costs nothing that was not already being paid.**
    """
    theme = getattr(getattr(st, "context", None), "theme", None)
    return str(getattr(theme, "type", None) or "light").lower() == "dark"


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(TABLE_CSS, unsafe_allow_html=True)


TABLE_CSS = """
<style>
/* THE OPAQUE GROUND A FROZEN COLUMN PAINTS ITSELF WITH, AND THE BAND BEHIND A GAME.
   Tokens, because they need a value in both themes: a hardcoded #fff is a white stripe down
   a dark page, and a TRANSPARENT sticky cell shows the scrolled content sliding underneath —
   the classic failure, and it reads as a rendering bug rather than a missing color.

   ⚠ BUILT FROM `Canvas` AND `CanvasText`, WHICH ARE LIVE. Two earlier attempts asked the
   wrong source and both were wrong in a way Marc could see:

     prefers-color-scheme  answers what the OPERATING SYSTEM prefers. A reader on a dark
                           system who switches the app to Light gets a light page painted
                           with dark cells — which is what happened.
     st.context.theme      answers what the app is rendering, but only when Python next
                           runs. Switching the theme repaints immediately and the tokens
                           lag a rerun, so some frozen cells kept the old color until a
                           tab change forced another pass. Marc: "seems like there might be
                           something upstream that isn't getting touched."

   Streamlit sets `color-scheme: light|dark` on its own container from the ACTIVE theme
   (verified in its bundle: `colorScheme: isLight ? light : dark`, beside `backgroundColor:
   colors.bgColor`). CSS system colors follow that property, so `Canvas` IS the page and
   `CanvasText` IS the text — with no Python in the loop and nothing to go stale. The theme
   switch repaints these in the same frame it repaints everything else.

   `color-mix` derives the rest from the same two, so the band and the rules track the theme
   instead of being two more colors to keep in step. */
:root {
  --cfdb-sticky-bg: Canvas;
  --cfdb-band-bg:   color-mix(in srgb, CanvasText 6%,  Canvas);
  --cfdb-hover-bg:  color-mix(in srgb, CanvasText 10%, Canvas);
  --cfdb-muted:     color-mix(in srgb, CanvasText 62%, Canvas);
  --cfdb-rule:      color-mix(in srgb, CanvasText 20%, Canvas);

  /* R-552. THE TOKENS THAT REPLACED THE `prefers-color-scheme` BLOCK AT THE END OF THIS FILE.
     R-547 converted three declarations and left this one, which is the last live instance in
     `site/`. Same reasoning, so it is deleted rather than corrected: it asked the OPERATING
     SYSTEM, Marc's Mac is dark, his Streamlit theme is Light, and every rule the block carried
     was therefore painting a dark page's colors onto a light one — links and table rules
     included, on his screen, right now.

     TWO DIFFERENT TOOLS, BECAUSE THE BLOCK CARRIED TWO DIFFERENT KINDS OF COLOR.

     A NEUTRAL RULE IS A TINT OF THE PAGE, so `color-mix` on Canvas/CanvasText derives it and
     no second value is needed. The percentages are measured from the two hardcoded values
     they replace, not guessed — #d7dae0 on white is 14.1% black and #333a45 on #0e1117 is a
     17.5% lift, so 16% reproduces both within a shade; #eef0f3/#242933 are 5.8%/10.4%, so 8%. */
  /* 🚨 A192 (cfdb-main-R-2014). THE PLAYER CARD'S THREE WIDTHS, EVERY ONE MEASURED IN A REAL
     BROWSER RATHER THAN CHOSEN — see `.cfdb-card` for the table they came from, and
     `ci/measure_player_card.py`, which re-derives them and fails if they go stale.

     ⚠️ THEY ARE CUSTOM PROPERTIES SO THE NUMBERS HAVE ONE HOME. A191 spent a round on six
     header widths that existed twice — once in the page and once hand-copied into a test —
     and the copies disagreed while the test stayed green. */
  /* 🚨 2.75rem, AND THE FIRST TWO VALUES HERE WERE BOTH WRONG FOR THE SAME REASON.
     📊 A192 read the widest abbreviation as 28.3px and cut this track to 30px — and then
     measured **78 of 150 abbreviations clipped**, because that 28.3 was a `Range` over an
     element that was ALREADY ellipsised, which returns its box and not its text. Cloning
     each into an off-screen `nowrap` box gives the truth: **`MRMK` is 41.6px**, `WASH` 40.3,
     `UNCO` 40. ⚠️ THIRD TIME THIS ROUND that a Range over a clipped element understated a
     width — the header row in A191, the metric cells above, and this. **On this page, a
     measured width is only trustworthy if the thing measured was free to be its full size.** */
  /* 🚨 A212 (cfdb-main-R-2520) LOOKED AT THIS AND PUT IT BACK. 44px IS NOT THE CONSTRAINT.
     > **MARC, v14:** *"Cards with Ranked teams are word-wrapping an extra line."*
     📊 THE DEFECT IS REAL AND MEASURED: a ranked card's identity occupies THREE line bands —
     logo (28px) / rank badge (12.2–18.3px) / abbreviation — and is 59.2px tall against an
     unranked card's two bands and 43.2px. That 16px is the extra line, on 12 of 150 cards,
     every one of them ranked.
     🚨 BUT WIDENING THIS DOES NOT FIX IT, WHICH IS THE FINDING. Raised to 3.125rem (50px) and
     re-measured: the bands stayed at three. **28 + 1.6 gap + 12.2 badge = 41.8px fits inside
     44px, let alone 50** — so the badge is not wrapping for want of room, and the arithmetic
     that said it was (47.9px against 44) used the widest badge rather than this card's.
     ✅ A213 (cfdb-main-R-2545) EXPLAINED BOTH, AND THE SECOND FOLLOWS FROM THE FIRST. The box
     drew 28px because `logo_or_monogram` writes the size as an INLINE STYLE, which no
     selector can beat — the 18px rule was never in the contest. And with two margins nobody
     had counted (logo `margin-right:.4rem`, rank `margin-left:.3rem`) the first band needed
     **54.57px**, so a 50px slot could not have held it either. **A212's revert was correct
     and this note records why, rather than leaving the number looking arbitrary.** */
  /* 🚨 A221 (cfdb-main-R-2689): 57.6px, AND THE NUMBER IS FROM A MEASUREMENT. The rank now
     shares the abbreviation's line, so the slot has to hold `#20 MRMK` rather than `MRMK`
     alone: the widest badge draws 18.25px, the flex `column-gap` is 3.2px, and the widest
     abbreviation is 41.6px — 63.05px if all three worst cases land on one card, 57.6 for the
     realistic pair. ⚠️ THE EXTRA 13.6px COMES OUT OF THE NAME'S FLOOR, which is the gap PART 1
     reclaimed; see `--cfdb-card-name-min` for what that costs and why it is affordable. */
  --cfdb-card-team-w:    3.6rem;   /* 57.6px; was 44px for `MRMK` alone */
  /* 🚨 THE METRICS BLOCK IS CONTENT-SIZED, NOT A TRACK, AND THE FIRST ATTEMPT AT A TRACK WAS
     WRONG IN A WAY A192 HAD ALREADY BEEN WARNED ABOUT. It was set to 72px from a measurement
     that summed each metric's own need (66.6px) — but `.cfdb-card-metric` is `flex:1 1 0`,
     **equal thirds**, so the widest single cell governs all three. 📊 And the re-measurement
     understated it too: a `Range` over a cell that has ALREADY WRAPPED returns its wrapped
     box, which is A191's header trap exactly. Cloning each cell into an off-screen `nowrap`
     box gives the real figure — **25.4px for a three-digit value** — so equal thirds need
     3 x 25.4 + 2 x 4 = 84.2px, and 30 of 180 cells were wrapping inside 72px.
     ✅ Sizing to content removes the constant entirely: the block asks for what it draws, and
     a card of two-digit values hands the difference back to the name. */
  /* 🚨 THE FLOOR IS THE SURNAME ALONE (109.2px + slack), NOT the surname PLUS the jersey.
     📊 Measured: at 1100px the card's content box is 158.9px, so team(36) + gap + jersey(27.2)
     + gap + surname(109.2) = 185.2 cannot share a line however the tracks are cut. Setting the
     floor to 144 made the flex row wrap in the worst order — **the team alone on line one**,
     the name on line two, the metrics on line three, a 156.6px card. With the floor at the
     surname the jersey wraps ABOVE the name inside the cell instead, the team keeps the name
     company on line one, and the surname still cannot be squeezed. */
  /* 🚨 A221 (cfdb-main-R-2690): 108.8px, DOWN FROM 112, AND IT BUYS A UNIFORM JERSEY.
     📊 MEASURED BEFORE THE CHANGE: the jersey sat BESIDE the name on 16 of 30 yardage cards
     and ABOVE it on 14 — and cards in one row differed in height by 45%. **The driver was not
     the name: it was the metrics block.** `.cfdb-card .cfdb-player-row` wraps, so the jersey
     shares the name's line only when `who` is wide enough for 25.6px of jersey, a 6.4px gap
     and the name's floor — and `who` is whatever the metrics block left over, which varied
     with how many digits the metric happened to have.
     ✅ THE FLOOR IS UNCHANGED AT 7rem, AND THAT IS THE POINT OF THE FIX BELOW. Squeezing it
     to 6.8rem to let the jersey share the name's line was tried and measured: it left the
     jersey beside the name on Defense's 10 of 30 and above it on the other 20, because `who`
     still differs by board and the wrap still depended on which side of a threshold it fell.
     **A layout that depends on a threshold is a layout that will cross it again.**
     🚨 SO THE JERSEY IS GIVEN ITS OWN LINE UNCONDITIONALLY (see `.cfdb-player-jersey` below),
     which is deterministic, costs no overflow, and is what 1024 already did — one layout at
     both widths instead of two. */
  --cfdb-card-name-min:  7rem;     /* 112px; widest real surname "Chambers-Smith" is 109.2 */
  --cfdb-edge:      color-mix(in srgb, CanvasText 16%, Canvas);
  --cfdb-rule-soft: color-mix(in srgb, CanvasText 8%,  Canvas);

  /* A BRAND HUE IS NOT A TINT, AND `color-mix` IS THE WRONG TOOL FOR IT. Mixing #1f6feb
     toward CanvasText lifts it on dark (right) and darkens it on light (wrong) — there is no
     single percentage that leaves the light value alone, because CanvasText points the
     opposite way in each theme. `LinkText` is wrong too: it is the browser's default link
     color, so it would discard the brand blue and differ between browsers.

     `light-dark()` is the tool. It follows the SAME `color-scheme` property Streamlit sets
     from the ACTIVE theme that Canvas/CanvasText follow, so it switches in the same frame and
     keeps both deliberately-chosen values. The dark value is not a different color — R-131
     measured #1f6feb on #0e1117 at about 3.6:1, below the 4.5:1 a small glyph needs, and
     #58a6ff is the contrast lift that clears it. Same for the three underperformer tiers. */
  --cfdb-link: light-dark(#1f6feb, #58a6ff);
  /* 🚨 A239 (cfdb-main-R-3234). THE IQR TINT — Marc, v19: *"a dark orange, like burnt
     sienna"*, on the p25/p75 numbers AND on the box they describe, so a reader sees the two
     numbers ARE the box.
     📊 A PAIR, BECAUSE ONE LITERAL CANNOT SERVE BOTH SCHEMES AND THIS ROUND MEASURED IT.
     Marc's `#8A3324` is **8.14:1 on the light canvas** — comfortably past AA — and **2.32:1 on
     `#0e1117`**, which is below even the 3:1 floor for non-text. Unreadable in a scheme the site
     ships. `#E07B5A` is the same hue lightened and scores **6.43:1 on dark** (and its own 2.94
     on light, which is why it is not used there). Both halves therefore pass AA for body text
     in the scheme they serve.
     ⚠️ `distribution.py` references this as `var(--cfdb-iqr)` rather than carrying its own hex:
     `CSS` here is a plain string, not an f-string, so the literal cannot travel the other way
     without escaping every brace in the stylesheet. ONE definition, and this is the end that
     does not rewrite it. */
  --cfdb-iqr:  light-dark(#8A3324, #E07B5A);
  /* 🚨 A211 (cfdb-main-R-2503). THE OUTCOME BANDS WERE SEPARATED BY HUE AND NOT BY LUMINANCE,
     AND THE NUMBERS SAY SO.
     > **MARC, v14:** *"The color scale on the Outcome cicrle glyph is too hard to
     > differentiate. Change 8-14 to a light/medium gray, 15+ to a dark/black."*
     📊 MEASURED as WCAG contrast between the bands as they stood — amber, orange, red:
         light   u1|u2 1.46:1   u2|u3 1.48:1        dark   u1|u2 1.45:1   u2|u3 1.28:1
     ⚠️ EVERY ADJACENT PAIR WAS UNDER 1.5:1, which is what "too hard to differentiate" is when
     it is a number. R-141 made these three differ by COLOR ALONE on purpose; that only works
     if the colors are far apart, and three warm hues at one luminance are not.
     ✅ AFTER: a luminance ramp, which a grayscale or color-blind reader can also read —
         light   u1|u2 2.79:1   u2|u3 2.79:1        dark   u1|u2 2.28:1   u2|u3 3.84:1
     ⚠️ `u2` IS MEDIUM RATHER THAN LIGHT GRAY, AND THAT IS A TRADE WORTH NAMING. A light gray
     (#8b9099) reads 1.41:1 against the amber `u1` keeps — WORSE than today — and 3.2:1
     against the page, under the 4.5:1 this file already demands of a small glyph. Medium gray
     clears both.
     🚨 AND `u3` IS NEAR-WHITE IN DARK MODE, WHICH IS "dark/black" READ AS *the heaviest ink
     on the page*. Literal black on a #0e1117 ground is an invisible mark, and Marc is
     describing the light theme he looks at. Said here rather than decided silently.
     ⚠️ `u1` IS UNCHANGED — he did not name it, and the change does not collide with it. 📊 It
     is 2.27:1 against a white page, under the 4.5:1 floor, and that is PRE-EXISTING and
     reported rather than fixed in passing. */
  --cfdb-u1:   light-dark(#d9a406, #e8b931);
  /* 🚨 A223 (cfdb-main-R-2628). THE 8-14 BAND IS LIGHTENED 25% TOWARD ITS OWN PAGE.
     > **MARC, v16:** *"Upset by 8-14 is too dark, not very discernable from Upset by 15+ by
     > shade. Reduce the darkness by 25%, maybe 50%"*
     📊 THE WHOLE LADDER, RESOLVED IN A BROWSER AGAINST THE REAL PAGE — and the first probe
     got the ground wrong, which is worth recording: the app container is TRANSPARENT, so
     reading its `backgroundColor` returned `rgba(0,0,0,0)` and every "vs page" figure was
     computed against BLACK in both themes. Walk up to something that paints.
         light  page #ffffff   u1 #d9a406 2.27:1   u2 #5f5f67 6.33:1   u3 #16191d 17.63:1
         dark   page #0e1117   u1 #e8b931 10.27:1  u2 #7b7b83 4.50:1   u3 #f2f5f8 17.27:1
         steps  light u1|u2 2.79  u2|u3 2.79       dark u1|u2 2.28  u2|u3 3.84
     ⚠️ A211 BALANCED THOSE TWO STEPS DELIBERATELY, AND THE LADDER IS LUMINANCE-SATURATED:
     white -> amber -> gray -> near-black is the whole range, so widening one gap narrows the
     other. **Moving u2 up cannot be free.**
     ✅ IT IS STILL THE RIGHT TRADE, AND THE REASON IS WHAT SEPARATES EACH PAIR. `u2` and `u3`
     are both NEUTRAL GRAYS — luminance is the only signal they have. `u1` is AMBER, so `u1|u2`
     carries a hue difference as well. **Spend luminance where luminance is all there is.**
         25%  light u2 #87878d  vs page 3.57   u1|u2 1.58   u2|u3 2.79 -> 4.94
              dark  u2 #606068  vs page 3.03   u1|u2 2.28 -> 3.39      u2|u3 3.84 -> 5.69
         50%  light u2 #afafb3  vs page 2.19   dark #44464d  vs page 2.01
     🚨 **50% IS REJECTED BY MEASUREMENT, NOT BY TASTE: it puts the glyph under 3:1 against its
     own page in both themes** — WCAG 1.4.11's floor for a non-text graphical object, which is
     what a filled circle is. 25% clears it in both (3.57 and 3.03). ⚠️ A211 applied the 4.5:1
     TEXT floor to this glyph; the applicable one for a shape is 3:1, and that is why 25% ships.
     🚨 AND "TOWARD THE PAGE" IS NOT "LIGHTER" IN BOTH THEMES — R-547's lesson. In light mode
     it lightens; in dark mode the page is #0e1117, so the same move DARKENS. **Both directions
     mean less ink against the ground the reader is looking at**, and both improve the pair
     Marc named. The dark theme is not the mirror of the light one. */
  --cfdb-u2:   light-dark(#87878d, #606068);
  --cfdb-u3:   light-dark(#16191d, #f2f5f8);
}
.cfdb-table { width:100%; border-collapse:collapse; font-size:.9rem;
    table-layout:fixed; }

/* A138. THE SCOREBOARD INSIDE A CELL — away over home, quarters across, final at the right.
   Marc: "present each row like a scoreboard, Away over Home, each quarter, then final score."

   ⚠ NESTED INSIDE `.cfdb-table`, so every rule here has to UNDO something the outer table
   sets. `table-layout:fixed` on the outer one does not inherit, but the font size, the cell
   padding and the header opacity all reach in and have to be answered explicitly — an inner
   table that quietly takes the outer's 90% header opacity reads as disabled.

   ⚠ `width:auto`, NOT `100%`: the scoreboard is as wide as its own numbers and is not stretched
   across a cell sized for the longest team name on the page. */
/* 🚨 `table-layout:fixed` AND FIXED CELL WIDTHS, AND THE RASTER IS WHY — TWICE. With the
   columns sized to their content, a row with two-digit quarters was wider than a row without,
   so the "4" was in a different place on every game and a reader scanning ten scoreboards had
   to re-find it each time. A scoreboard's whole value is that the same number is always in the
   same place. Widths are per-column rather than on the table, so an overtime game is simply one
   column wider than a regulation one. */
.cfdb-table td .cfdb-scoreboard { width:auto; border-collapse:collapse;
    font-size:.88em; table-layout:fixed; }
.cfdb-table td .cfdb-scoreboard th,
.cfdb-table td .cfdb-scoreboard td { width:1.75rem; }
/* 🚨 A165 (cfdb-main-R-1302). VERTICAL PADDING GOES TO ZERO HERE AND ONLY HERE.
   > **MARC, Today v05:** *"Too much vertical padding below the Scoreboard and Win Probability.
   > We need things more dense vertically."*

   📊 THE ROW WAS DECOMPOSED BEFORE ANYTHING WAS CUT, because the obvious term was not the
   largest. At a 1300px viewport the Most Exciting row is **94.2px**:

       away row + home row        67.2px   <- driven by the 28px LOGO, the single largest term
       scoreboard thead (1 2 3 4 F) 13.6px
       .cfdb-table td padding x2  13.44px  <- EVERY TABLE ON THE SITE. Eighteen pages.

   ✅ **THE TWO TERMS CUT HERE ARE THE ONLY ONES SCOPED TO THIS PANEL**: this rule's own
   `.05rem` of vertical cell padding, and the thead's line-height. Together they take the row to
   **87.8px** and a ten-row panel from **935.5px to 871.6px — 63.9px returned**, with the header
   labels (`today.py`) returning a further 15px at that width.

   ⚠️ **THE LOGO IS THE BIGGER LEVER AND IT IS NOT THIS ROUND'S TO PULL.** 28px -> 22px takes the
   row to 82.2px and the panel to 815.5px — nearly twice this saving — but a logo is an identity
   affordance on Marc's page (§2.1), so it is measured, rendered and handed to him rather than
   changed. ❌ **And `.cfdb-table td`'s 6.72px is not touched**, for the reason A164 gave and was
   right about: it is Schedule, Team, Odds and fifteen others.

   ⚠️ HORIZONTAL PADDING IS UNCHANGED — `.3rem` still separates the quarter columns, and the
   `border-spacing` was measured and returns nothing (0.0px), so it is left alone. */
.cfdb-table td .cfdb-scoreboard th,
.cfdb-table td .cfdb-scoreboard td { padding:0 .3rem; border:0; opacity:1;
    text-align:right; white-space:nowrap; font-weight:400; }
/* The quarter labels are a scale, not data: muted, so the numbers under them read first.
   ⚠️ A165: `line-height:1` — these are five short glyphs and the leading above them was
   3.2px of the row. They are the only text in the scoreboard that is not a number. */
.cfdb-table td .cfdb-scoreboard thead th { font-size:.82em; opacity:.6;
    letter-spacing:.02em; line-height:1; }
/* The team is the row's name and reads left; everything after it is a number and reads right. */
/* A FIXED WIDTH, NOT A MAX, AND THE RASTER IS WHY. With the column sized to its content every
   scoreboard was a different width, so the quarter columns did not line up down the page and a
   reader scanning ten games had to re-find the "4" on every row. A scoreboard's whole value is
   that the same number is always in the same place. Long names ellipsise rather than widening
   the grid.

   🚨 A165 (cfdb-main-R-1301): 9.5rem -> 13rem, AND THIS IS WHERE MARC'S TRUNCATION ACTUALLY WAS.
   > **MARC:** *"We need to grant Scoreboard more horizontal space because with the Record added
   > its truncating team name."*

   📊 **HIS DIAGNOSIS POINTED AT THE OUTER COLUMN AND THE MEASUREMENT SAYS OTHERWISE.** Widening
   the Scoreboard column from 288px to 443px — **+54%** — left the ellipsised-name count at
   **11, unchanged**, at both 1300px and 1600px. The name is clipped by THIS cell's fixed
   152px, not by the column that contains it, so no amount of outer width could ever have
   reached it. ⚠️ **The cause is real and his sentence names it exactly: A164 added the record
   INTO this fixed cell**, and the room it needed came out of the name.

   📊 SWEPT RATHER THAN GUESSED — clipped names at 1300px and 1600px, logo untouched at 28px:
   9.5rem -> 10 · 11rem -> 3 · 12rem -> 2 · **13rem -> 0** · 14rem -> 0.

   ✅ **13rem IS THE FIRST WIDTH THAT CLIPS NOTHING, AND IT IS STILL FIXED** — which is the whole
   property the paragraph above protects. Every scoreboard on the page remains the same width and
   the quarter columns still line up. **The rule changed its number, not its kind.** */
.cfdb-table td .cfdb-scoreboard .cfdb-sb-team { text-align:left; padding-right:.5rem;
    font-weight:500; width:13rem; max-width:13rem; overflow:hidden; text-overflow:ellipsis;
    white-space:nowrap; }
/* THE FINAL SCORE IS THE ONE NUMBER A READER LOOKS FOR, and a scoreboard sets it apart from
   the quarters it is the sum of. A rule rather than bold: bold on both lines would compete
   with the team names for the same emphasis. */
.cfdb-table td .cfdb-scoreboard .cfdb-sb-final { font-weight:600; padding-left:.5rem;
    width:2.6rem; border-left:1px solid var(--cfdb-edge); }
/* AWAY OVER HOME IS THE LAW (R-522) AND THE HOME SIDE CARRIES THE ONLY DIVIDER, so the two
   lines cannot be read as an unordered pair. */
.cfdb-table td .cfdb-scoreboard .cfdb-sb-home th,
.cfdb-table td .cfdb-scoreboard .cfdb-sb-home td { border-top:1px solid var(--cfdb-edge); }

/* R-269. HORIZONTAL SCROLLING, WHICH THE PERCENTAGE LAYOUT MADE IMPOSSIBLE.
   `width:100%` plus a percentage colgroup cannot overflow — thirty-nine columns compress
   until unreadable and there is nothing wider than the viewport to scroll. `max-content`
   lets the colgroup's pixel widths set the table's width; `min-width:100%` keeps a narrow
   table filling the page rather than shrinking to its content. Opt-in, because the other
   seventeen callers of render() want neither. */
/* R-281. THE CONTAINER HAD NO HEIGHT, SO THE HORIZONTAL BAR WAS 5,300px BELOW THE FOLD.
   Measured on the running page: scrollHeight 6275 / clientHeight 6275, max-height none, in a
   917px window — horizontal scrolling was reachable only after scrolling the whole page down.
   Constraining the height puts the bar at the bottom of the visible box, where the reader is
   looking, and gives the table its own vertical scroll. */
.cfdb-scroll { overflow-x:auto; overflow-y:auto; max-height:70vh;
    /* 🚨 A208 (cfdb-main-R-2263). THE SCROLLBAR IS STYLED FOR EVERY WIDE TABLE, AND IT IS NOT
       WHAT THE READER DEPENDS ON. A207 measured this on the SLATE: `overflow-x:auto` says
       content exists past the box and says NOTHING about whether a reader can tell, because
       macOS draws an OVERLAY bar that exists only while something is scrolling.
       📊 A207's measurement, kept because A208 did not repeat it: with these declarations in
       the page and `scrollbar-width:thin` computing, `offsetHeight - clientHeight` stayed
       **0px at every width**. 🚨 AN EARLIER VERSION OF THIS COMMENT ASSERTED THE OPPOSITE:
       that these two declarations together take up layout space and so make the fix
       measurable. ⚠️ THAT IS THE APPROACH A207 ABANDONED, and its reasoning shipped anyway —
       left in the shared file, beside the styling it argued for, where the next reader would
       have learned a mechanism this project measured as not working. It is corrected rather
       than deleted: the styling is kept because a platform that draws classic scrollbars respects
       it, and a future reader needs to know it was never PROVEN drawn in this one.
       ✅ The affordance a reader actually depends on is `.cfdb-scrollnote` below. */
    scrollbar-width: thin;
    scrollbar-color: color-mix(in srgb, currentColor 35%, transparent) transparent; }
.cfdb-scroll::-webkit-scrollbar { height:10px; }
.cfdb-scroll::-webkit-scrollbar-track {
    background:color-mix(in srgb, currentColor 8%, transparent); border-radius:5px; }
.cfdb-scroll::-webkit-scrollbar-thumb {
    background:color-mix(in srgb, currentColor 32%, transparent); border-radius:5px; }
.cfdb-scroll::-webkit-scrollbar-thumb:hover {
    background:color-mix(in srgb, currentColor 48%, transparent); }

/* 🚨 A208. THE NOTE IS KEYED TO EACH TABLE'S OWN MINIMUM, NOT TO ONE HARD-CODED 939.
   A207 shipped `@container (max-width: 939px)` for the SLATE alone. Four wrappers on this
   site use `.cfdb-scroll` and they have four different boundaries, so ONE number in the
   stylesheet could only ever be right for one of them — a note that appears where nothing is
   hidden is worse than no note, because it teaches readers to ignore it.
   ✅ So the boundary travels with the table: `table.scroll_note(min_px)` emits the note AND
   the one `@container` rule that reveals it, keyed on `[data-min]`. The stylesheet holds the
   shape; the caller holds the number, and it is the SAME number the table's own `min-width`
   is set from — one definition, in Python, per table.
   ⚠️ HIDDEN BY DEFAULT AND REVEALED BY THE QUERY, never the other way round: with no
   container-query support a reader gets a note that is mildly redundant rather than a table
   that silently hides five columns.
   ⚠️ `container-type:inline-size` ASKS ABOUT THE SECTION, NOT THE VIEWPORT — the sidebar's
   width changes the answer and a media query cannot see it. */
/* 🚨 A211 (cfdb-main-R-2501). THE CLOSE-LINE CONTROL STOPS SPANNING THE SECTION.
   > **MARC, v14:** *"The Close Line withing drop-down menu shouldn't span the full width of
   > the page. Reduce to 10-25% of the page."*
   📊 MEASURED FIRST: it spanned **980px of a 980px section at 1440, and 564 of 564 at 1024** —
   100% at both, which is Streamlit's default for a widget in a full-width block.
   ⚠️ A PERCENTAGE ALONE WOULD CLIP IT AT THE NARROW END. 25% of 564 is 141px, and the widest
   option — `8 points` — plus the chevron needs more than that at Streamlit's own font. So the
   width is a percentage with a PIXEL FLOOR: 22% of the section, never below what the longest
   string needs. At 1440 that is ~216px (22%); at 1024 the floor wins and it sits at the
   floor, which is still ~34% of a much narrower section and is the honest trade.
   ⚠️ THE LABEL AND THE HELP ICON TRAVEL WITH IT because they are the widget's own children —
   constraining the container constrains all three, which a narrow control under a full-width
   label would not.
   ⚠️ SCOPED BY THE WIDGET'S KEY. Streamlit stamps `st-key-<key>` on the element container when
   a `key=` is given; `_close_cut_control` passes `key="today_close_cut"`, and the class was
   confirmed present in the browser before this rule was written rather than assumed. */
.st-key-today_close_cut { width:22%; min-width:var(--cfdb-close-cut-floor, 170px); }

.cfdb-scrollbox { container-type:inline-size; }
.cfdb-scrollnote { display:none; font-size:.7rem; opacity:.75; margin:.1rem 0 .3rem;
    gap:.3rem; align-items:center; }
/* 🚨 A209 (cfdb-main-R-2452). THE SCROLL SENTENCE IS A CLAUSE, NOT THE WHOLE NOTE.
   One line has to be able to carry two facts that become true at DIFFERENT widths — the SLATE
   puts two columns away below 940 and does not overflow until 820 — and a clause that is
   always on would be false between them. `table.scroll_note` reveals the element at one
   boundary and this span at the other; where a caller gives only one, both fire together and
   the line reads exactly as A208 shipped it. */
.cfdb-scrollnote-scroll { display:none; }

/* 🚨 A209 (cfdb-main-R-2451). THE SLATE PUTS `O/U` AND `Wx` AWAY WHERE THEY CANNOT ALL FIT.
   > **MARC, 2026-09-22:** *"YES, make this happen, with the fix to have column say it's
   > hidden."*
   ⚠️ THIS REVERSES NOTHING FROM A204. There he asked for every column and at full width he
   still gets every column; this is the narrow case, which he had not been shown then.

   🚨 `display:none` ON THE CELLS WOULD HAVE SHIFTED EVERY COLUMN IN THE ROW, AND IT WOULD HAVE
   LOOKED LIKE DATA. `table-layout:fixed` maps the Nth cell to the Nth `<col>`, so removing two
   cells leaves seven cells reading nine columns' widths: measured on paper, the gantt would
   have inherited `Why`'s 54px. ✅ So the cells STAY and collapse to zero — the mapping is
   never disturbed, and the header and the body collapse by the same rule, together.
   ⚠️ `!important` IS LOAD-BEARING, NOT A SHORTCUT: the widths are inline `style` attributes
   written per table by `views/today.py`, and a stylesheet rule cannot beat an inline one
   without it. The boundaries live in Python with the widths they are derived from. */
.cfdb-slate-putaway { display:none; }
/* AND THAT MAKES A STICKY HEADER NECESSARY, NOT MERELY POSSIBLE. Prompt 044 put it out of
   scope because vertical stickiness inside Streamlit's own scroll container is a separate
   problem — a reason that expires the moment the table owns its vertical scroll. With 166
   rows scrolling inside the box, a header that scrolls away is worse than what was fixed. */
.cfdb-scroll .cfdb-table thead th { position:sticky; top:0;
    background:var(--cfdb-sticky-bg); z-index:3;
    /* ⚠ opacity:1 IS THE WHOLE FIX FOR THE GHOSTING, AND IT IS NOT A STYLE PREFERENCE.
       `.cfdb-table th` carries opacity:.65, which was harmless while headers were opaque
       against the page — but OPACITY APPLIES TO THE WHOLE CELL, background included. A 65%
       header cannot hide anything sliding under it, so rows scrolled through their own
       column labels and the two sets of text overlapped. Marc: "Can we mute the fields when
       they slide behind. I find that more distracting than informative."
       The muting the opacity was doing is now done by COLOR, which does not make the cell
       see-through. Same for the frozen body cells below. */
    opacity:1; color:var(--cfdb-muted,#5d6672); }
.cfdb-scroll .cfdb-table td.cfdb-sticky { opacity:1; }
/* THREE LAYERS NOW, AND THE CORNER IS THE ONE THAT BREAKS. A cell that is both frozen-left
   and in the sticky header must outrank both; at equal z-index it renders in DOM order and
   looks fine until a row scrolls under it. */
.cfdb-scroll .cfdb-table thead th.cfdb-sticky { z-index:4; }
.cfdb-table-wide { width:max-content; min-width:100%; }
/* A189: a scrolling table whose every column is a measured px takes exactly that width and no
   more. `min-width:100%` would share the leftover out as cell padding — which is the "lot of
   padding to the right of the scoreboard" Marc reported, reappearing on a wide screen. */
.cfdb-table-wide.cfdb-table-exact { min-width:0; }
.cfdb-table th.cfdb-sticky, .cfdb-table td.cfdb-sticky {
    position:sticky; background:var(--cfdb-sticky-bg); z-index:2; }
/* The header's frozen cells sit above the body's, or a scrolled row paints over them at the
   intersection. */
.cfdb-table th.cfdb-sticky { z-index:3; }
/* R-282. Denser rows, which is the other half of Marc's ask. The headers wrap because the
   columns got narrower; the rows get shorter because the padding did. */
.cfdb-table-wide td { padding:.22rem .45rem; }
.cfdb-table-wide th { padding:.3rem .45rem; vertical-align:bottom; }
/* Where the frozen block ends. Without it the reader cannot tell which columns are pinned
   and which merely happen to be at the left edge. A box-shadow rather than a border because
   a border would change the column's width and push the sticky offsets out by a pixel each. */
.cfdb-table .cfdb-sticky-edge { box-shadow:1px 0 0 var(--cfdb-edge); }
/* The row hover is translucent, so it would let the scrolled content through on a frozen
   cell. Opaque equivalents of the same tint, over each theme's own ground. */
.cfdb-table tbody tr:hover td.cfdb-sticky { background:var(--cfdb-hover-bg); }
/* R-267. Alternating RUNS of one game, so a game's two rows read as a unit. Shaded on the
   row and repeated on its frozen cells, which are opaque and would otherwise stay white. */
.cfdb-table tbody tr.cfdb-gameband > td { background:var(--cfdb-band-bg); }
.cfdb-table tbody tr.cfdb-gameband > td.cfdb-sticky { background:var(--cfdb-band-bg); }
/* R-270. Back to the compound default. Rendered only while a user sort is active, so it is
   never a control that does nothing. */
/* R-283. THE TAB BAR. It went out as bare anchors — classes emitted, no rules written — so
   six tabs rendered as a run of underlined links with no spaces between them. They are
   anchors because the tab has to live in the URL; they should not LOOK like prose links. */
.cfdb-tabbar { display:flex; gap:.25rem; flex-wrap:wrap; margin:.2rem 0 .6rem;
  border-bottom:1px solid var(--cfdb-rule,#d7dae0); }
.cfdb-tab { display:inline-block; padding:.35rem .8rem; font-size:.85rem; font-weight:600;
  color:inherit; opacity:.6; text-decoration:none; border:1px solid transparent;
  border-bottom:none; border-radius:5px 5px 0 0; margin-bottom:-1px; }
.cfdb-tab:hover { opacity:.9; text-decoration:none; background:var(--cfdb-band-bg); }
.cfdb-tab-on { opacity:1; border-color:var(--cfdb-rule,#d7dae0);
  background:var(--cfdb-sticky-bg); }
.cfdb-resetsort { display:inline-block; font-size:.8rem; font-weight:600; color:var(--cfdb-link);
  text-decoration:none; border:1px solid var(--cfdb-edge); border-radius:4px;
  padding:.2rem .55rem; margin-bottom:.4rem; }
.cfdb-resetsort:hover { text-decoration:underline; }
.cfdb-resetsort-note { font-size:.75rem; opacity:.55; margin-left:.5rem; }
/* R-271. The globe sits INSIDE a text link, so it needs the baseline nudge the icon-only
   marks do not — without it the word rides high against the drawing. */
.cfdb-icon-inline { width:.95em; height:.95em; vertical-align:-.13em; margin-right:.25em; }
/* 🚨 A218 (cfdb-main-R-2640). NOTHING SPLITS A TOKEN IN HALF — NOT A NUMBER, NOT A WORD.
   📊 A217 put `overflow-wrap:normal` on `.cfdb-num` and left the text columns alone, because
   its prompt framed the defect as *a header may wrap; a value may not*. The defect is a KIND
   OF BREAK, not a kind of column: measured after A217 shipped, Schedule's TV column still
   split `ESPN` after `ESP` and `CBSSN` after `CBSS` — 10 cells at 1440 and 14 at 1280.
   ⚠️ A NETWORK NAME IS ONE TOKEN, EXACTLY LIKE A NUMBER. `ESP` / `N` reads as two things on a
   row that still looks complete, which is the defect A217 was written to end.
   ✅ So `normal` goes on EVERY cell. Streamlit's own stylesheet sets `break-word` here, and
   this is what overrides it. */
.cfdb-table td, .cfdb-table th { overflow:hidden; text-overflow:ellipsis;
    overflow-wrap:normal; }
/* 🚨 A218 (cfdb-main-R-2641). A HEADER BREAKS ITS WORD RATHER THAN LOSING IT.
   📊 A217's own after-crops show `SPRE…` at 1440 and `SPR…` at 1280: the label truncated
   because `white-space:nowrap` was applied to `th.cfdb-num` as well as `td.cfdb-num`.
   🚨 FOR A LABEL THE TRADE GOES THE OTHER WAY ROUND FROM A VALUE. A truncated number is
   visibly incomplete and the reader knows to look elsewhere; a truncated LABEL loses the word
   and there is nothing to recover it from. `SPREA` / `D` is ugly; `SPRE…` is a column nobody
   can name. **Complete beats tidy in the header row.**
   ⚠️ SCOPED TO `th`. A value must never take this license — that is R-2640 above, and the
   whole reason this rule is separate rather than folded into the one before it. */
.cfdb-table th { overflow-wrap:break-word; }
.cfdb-table caption { caption-side:top; text-align:left; font-size:.8rem; opacity:.6;
  padding-bottom:.4rem; }
.cfdb-table th { text-align:left; font-weight:600; font-size:.78rem; letter-spacing:.02em;
  text-transform:uppercase; opacity:.65; border-bottom:1px solid var(--cfdb-edge);
  padding:.45rem .55rem; }
.cfdb-table td { padding:.42rem .55rem; border-bottom:1px solid var(--cfdb-rule-soft); }
.cfdb-table tbody tr:hover { background:rgba(31,111,235,.05); }
/* Linked rows. The anchor fills the cell so the whole row is a target, while staying a
   real <a href> — which is what makes middle-click and copy-link work (AC-G.13). The row
   link inherits color so a table does not turn into a wall of blue; the column-specific
   link (a team name) is visually distinct, per AC-2.5. */
.cfdb-table td a.cfdb-cell-link { display:block; color:inherit; text-decoration:none;
    margin:-.42rem -.55rem; padding:.42rem .55rem; }
.cfdb-table td a.cfdb-cell-link-alt { color:var(--cfdb-link); font-weight:600; }
.cfdb-table td a.cfdb-cell-link-alt:hover { text-decoration:underline; }
.cfdb-table tr.cfdb-linked { cursor:pointer; }
.cfdb-dataset { font-size:.78rem; opacity:.72; margin:-.25rem 0 .6rem; }
.cfdb-dataset a { color:#1f6feb; text-decoration:none; }
.cfdb-dataset a:hover { text-decoration:underline; }
.cfdb-footer a { color:#1f6feb; text-decoration:none; }
.cfdb-footer a:hover { text-decoration:underline; }
.cfdb-footer-links { opacity:.85; }
/* The icon links sit in a line of .82rem text, so an icon at 1em would read as smaller than
   the words beside it — a drawing needs more box than a letter to carry the same weight.
   Sized in `em` so it stays proportional if the footer's font-size ever changes, and given
   its own line-height so the taller box does not push the footer's two lines apart. */
.cfdb-icon { width:1.45em; height:1.45em; vertical-align:-.36em; }
.cfdb-footer-links a.cfdb-icon-link { display:inline-block; line-height:1;
    margin:0 .05em; }
.cfdb-footer-links a.cfdb-icon-link:hover { opacity:.7; text-decoration:none; }
/* AC-G.18b. The neutral form states the scope; the active form marks it, because a
   filter inherited from another page has to be legible on arrival rather than inferable
   from the URL. */
.cfdb-scope { font-size:.82rem; opacity:.8; margin:.1rem 0 .7rem; }
.cfdb-scope-active { opacity:1; }
.cfdb-monogram-empty { display:inline-block; vertical-align:middle; border-radius:50%;
    background:rgba(127,127,127,.14); margin-right:.4rem; }
.cfdb-table th a.cfdb-sort { color:inherit; text-decoration:none; display:block; }
.cfdb-table th a.cfdb-sort:hover { text-decoration:underline; }
.cfdb-sort-arrow { opacity:.35; margin-left:.25rem; font-size:.7rem; }
.cfdb-table th.cfdb-sorted .cfdb-sort-arrow { opacity:1; }
/* R-133. THE SPACER'S WIDTH IS IN `em`, SO IT ONLY MATCHES WHILE THE FONT SIZES MATCH.
   Both carry the same font-size deliberately: if the spacer stops resolving to the glyph's
   width the two scores stop aligning vertically, which is the whole thing R-120 was built to
   prevent and the reason the size is stated twice rather than inherited. */
.cfdb-winner { color:var(--cfdb-link); font-weight:700; margin-right:.15rem;
               font-size:1.3rem; line-height:1; vertical-align:-.1em; }
.cfdb-winner-spacer { display:inline-block; font-size:1.3rem; width:.75em; }
/* R-135: in the card the marker rides the team cluster, at the team name's size. */
.cfdb-gc-team .cfdb-winner, .cfdb-gc-team .cfdb-winner-spacer { font-size:1rem; }
.cfdb-gc-team .cfdb-winner { margin-left:.4rem; margin-right:0; }
/* R-131. MARC ASKED FOR BOLD AND BOLD IS NOT THE FIX, SO IT IS NOT WHAT THIS DOES.
   The problem on dark is LUMINANCE, not weight: #1f6feb on #0e1117 is about 3.6:1, and
   thickening a stroke that is already the wrong brightness buys very little. Size, opacity
   and — in the dark block below — a lighter blue are what make it legible. The blue also
   says the glyph is a link, which is R-134's ask for the card. */
.cfdb-details { opacity:.85; font-size:1.3rem; color:var(--cfdb-link); vertical-align:-.12em; }
/* R-101: the neutral-site glyph now shares a column with the matchup glyph, so it
   needs its own separation from it rather than a column border. */
.cfdb-neutral { opacity:.85; margin-left:.4rem; font-size:1.15rem; color:var(--cfdb-link);
                vertical-align:-.06em; }
/* R-107: a card is not a table cell, so it cannot borrow .cfdb-cell-link — that one
   is display:block to make a whole <td> the target, which inside a flex row would
   make the anchor a full-width item and undo R-105. */
.cfdb-teamlink { color:inherit; text-decoration:none; }
.cfdb-teamlink:hover { text-decoration:underline; }
.cfdb-table td a:hover .cfdb-details { opacity:1; }
.cfdb-scope-chip { display:inline-block; background:rgba(31,111,235,.12);
    border:1px solid rgba(31,111,235,.35); border-radius:999px; padding:.06rem .5rem;
    margin-right:.3rem; font-weight:600; font-size:.78rem; }
/* 🚨 A217 (cfdb-main-R-2620). A NUMBER IS ONE TOKEN AND MUST NEVER BE BROKEN INSIDE IT.
   📊 Schedule shipped `56.0` as `56.` / `0` and `51.5` as `51.` / `5` — in the O/U column, at
   1440 with the sidebar open, on the page Marc reads most. A figure split across two lines is
   worse than a clipped one: clipped, a reader knows something is missing; split, `51.5` reads
   as two numbers and the row still looks complete.
   🚨 THE CAUSE IS NOT OURS AND THAT IS WHY NOTHING HERE MENTIONED IT. `overflow-wrap` computes
   to **break-word** on every table cell — it comes from STREAMLIT's own stylesheet, and this
   file contains no `overflow-wrap`, `word-break` or `word-wrap` rule at all. `break-word`
   licenses a break INSIDE a token the moment the box is a hair too narrow, and the O/U column
   is a hair too narrow: it draws 52.4px against content that wants 52.3px.
   ✅ `normal` puts the token back together. `nowrap` then keeps a number on one line even when
   the column cannot hold it, and `.cfdb-table td` already carries `overflow:hidden` and
   `text-overflow:ellipsis`, so the honest failure is `56.…` — visibly truncated.
   ⚠️ SCOPED TO `.cfdb-num`, WHICH `Col.css` GIVES EVERY `num`, `signed` AND `plain` COLUMN, so
   this is one rule for every numeric column on the site rather than one column at a time. Text
   columns keep wrapping at spaces, which is what they should do — a team name on two lines is
   a layout, a number on two lines is a lie. */
.cfdb-table th.cfdb-num, .cfdb-table td.cfdb-num { text-align:right; }
/* ⚠️ A218: `nowrap` IS THE VALUE'S ALONE NOW. A217 gave it to `th` and `td` together through
   one selector, which is what truncated `SPREAD`. A number on two lines is a lie; a LABEL on
   two lines is merely ugly, and the header above may take the second line. */
.cfdb-table td.cfdb-num { white-space:nowrap; }
/* R-103: a third alignment. A single glyph plus a two-digit temperature is neither
   a number nor prose, and right-aligning it hung the column off its own header. */
.cfdb-table th.cfdb-center, .cfdb-table td.cfdb-center { text-align:center; }
/* CLIP, DO NOT WRAP. The Inline table carries eleven columns, and below about 1400px the
   team columns are genuinely tight — Marc resizes often (R-125), so it has to degrade
   gracefully rather than break. A name on two lines doubles the row height and reads as a
   fault; an ellipsis reads as "narrow window". R-085 already abbreviates past 18 characters,
   so this only fires on a viewport the Stacked view suits better anyway. */
/* R-145. Rank, name and record are three different sizes in one line, and default
   `vertical-align:baseline` on inline boxes lines up their own baselines — which for a 12px
   span beside a 16px one sits them at visibly different heights once the smaller box has its
   own line-height. Aligning them all to the largest text's baseline explicitly is what makes
   the three read as one line. */
.cfdb-team, .cfdb-rank, .cfdb-team-record { vertical-align:baseline; line-height:1.25; }
.cfdb-team { margin-left:.4rem; }
/* 🚨 A201 (cfdb-main-R-2091). `vertical-align:middle`, NOT `bottom`.
   > **MARC:** *"Team Name isn't vertically aligned with the Logo, Rank and Record"*

   📊 MEASURED before changing anything, by a Range over each text node at 1440 and 1100 with
   the sidebar open: the NAME sat 4.5px below the logo's center, 5.5px below the rank and 5.0px
   below the record — worst center spread 5.5px. ⚠️ The other three agree with each other to
   within 1px, so the name was the one element out, not the record or the logo.

   ⚠️ THE CAUSE IS THIS RULE'S OWN `display:inline-block`. An inline-block takes an explicit
   alignment, `bottom` put its BOX bottom on the line-box bottom, and a 19px name box next to a
   28px logo then hangs 4.5px low. The ellipsis cluster it travels with is unrelated and stays
   — A164 tested that cluster for a different bug and exonerated it.

   ✅ `middle` takes the worst spread to 1.0px, and the 0.5px that remains is the 28px logo
   box's own half-pixel. Centering every element instead reaches 0.5px and was NOT taken: it
   would have to touch `.cfdb-logo` and `.cfdb-logo-box`, which the cards, the legend and
   Matchup all read, to buy half a pixel nobody can see. */
.cfdb-table .cfdb-team { display:inline-block; max-width:100%; vertical-align:middle;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* R-132: no font-size — it sits in the row and reads at the row's size. */
.cfdb-rank { font-weight:700; opacity:.7; margin-left:.3rem; }
.cfdb-daygroup { font-weight:600; margin:1.1rem 0 .3rem; font-size:.95rem; }
/* R-088: the record sits beside the team name, smaller and regular weight — not its own
   column, which would cost a column's width for two characters. */
/* NOWRAP because "5-2" IS ONE TOKEN. Without it the browser treats the hyphen as a break
   opportunity and renders "5-" above "2" the moment the column is a few pixels tight — which
   it became when R-132 gave the rank badge the row's font size. A record split across two
   lines reads as a rendering fault, and it would bite at some viewport width regardless. */
/* A149. THE PLAYER CELL HAS TWO ENDS — Marc, Today v01: "[Jersey #, Name, Year (left
   aligned)], Position (right aligned within the Player cell)".

   ⚠️ FLEX INSIDE AN EXISTING CELL, which is R-166's own precedent one column over: `.cfdb-gc-time`
   right-aligns the result strip in the kickoff cell for exactly this reason, and its comment says
   why it is safe — "Flex INSIDE an existing cell changes nothing about the grid; adding a cell
   would." A fourth and fifth column for two characters each is the alternative.

   🚨 THE NAME GIVES UP PIXELS FIRST AND THE POSITION NEVER DOES. `min-width:0` on the left group
   is what actually lets the name ellipsise — a flex item defaults to `min-width:auto` and refuses
   to shrink below its content, so without this line the position is what gets pushed out. The
   name itself reuses `.cfdb-team`'s treatment (line 460) rather than restating it differently.

   ⚠️ THE JERSEY AND THE YEAR ARE SECONDARY WEIGHT, THE NAME IS NOT. Marc's bracket groups them as
   one identity; the name is the thing being read and the other two are its qualifiers, which is
   the same relationship `.cfdb-team-record` already has to `.cfdb-team`. Same opacity, for that
   reason rather than by coincidence. */
.cfdb-player { display:flex; align-items:baseline; justify-content:space-between; gap:.5rem; }
.cfdb-player-who { display:flex; align-items:baseline; gap:.35rem; min-width:0; }
.cfdb-table .cfdb-player-name { display:inline-block; max-width:100%; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; vertical-align:bottom; }
.cfdb-player-jersey { font-size:.78rem; font-weight:600; opacity:.6; white-space:nowrap; }
.cfdb-player-year { font-size:.75rem; font-weight:400; opacity:.65; white-space:nowrap; }
/* R-088's argument, reused: a position is two characters and does not deserve a column. */
.cfdb-player-pos { font-size:.75rem; font-weight:600; opacity:.7; white-space:nowrap; }

/* ── A166: THE PLAYER CARD BOARDS ──────────────────────────────────────────────────────────
   > **MARC:** *"Swtich to player cards. 3 columns for Yardage (QB, Receiving, Rushing)."*

   🚨 **COMPACT BY REQUIREMENT, NOT BY TASTE.** Marc asked for *"things more dense vertically"*
   in the round immediately before this one, and a card is inherently less dense than a table
   row — ninety cards where thirty rows were. 📊 So the vertical cost was measured rather than
   discovered: three 25-row tables were 3,266px at 1300px, and the three card grids are measured
   in the report against that number at the same width.

   ✅ **THE GRID IS WHAT PAYS FOR IT.** Three columns side by side means a board of thirty cards
   is ten cards tall, not thirty — so the card can afford three lines and still cost less height
   than the table it replaces. **A single-column card list would have been strictly worse than
   the table on every axis Marc cares about.**

   ⚠️ `minmax(0, 1fr)` RATHER THAN `1fr`: a grid track's default minimum is `auto`, which refuses
   to shrink below its content, so a long team name would push the column wider and break the
   three-up alignment instead of ellipsising. This is `.cfdb-player-who`'s `min-width:0` one
   level up, and the same reason. */
/* ── A178 (cfdb-main-R-1857): WHERE A SORT ANCHOR LANDS ───────────────────────────────────
   > MARC, v10: "It looks like the reloads the whold page then scrolls down to the section
   > link, but it's at the bottom of the page. Can we make it so that the header scrolls to be
   > the bottomw of the page? To make it better for the end-user?"

   ✅ BUILT AS READING (1): the sorted heading ends at the TOP of the viewport with its table
   below it, because "to make it better for the end-user" only makes sense if the thing he
   sorted is the thing he then sees. 📋 The other reading — the header literally at the BOTTOM
   of the viewport — is one word from him and one constant from here.

   🚨 AND THE MEASUREMENT CORRECTED THE STATED CAUSE. The premise was that Leaderboards sits
   too near the bottom for the browser to scroll that far. Measured on the real page at 1300 x
   900, 2025 week 8:

       Most exciting                  top 598    7470px below it   reaches the top
       How the week went ...          top 1632   6436px below it   reaches the top
       The week's movers              top 2739   5329px below it   reaches the top
       Offense and defense            top 3276   4792px below it   reaches the top
       Leaderboards                   top 4217   3852px below it   reaches the top
       Poll movement                  top 7934    134px below it   766px SHORT

   🚨 **ALL FOUR SECTIONS THAT CARRY A SORT ANCHOR ALREADY REACHED THE TOP** — Most exciting,
   the market, the movers and Leaderboards, the last of which has 3,852px of page beneath it.
   The prompt's premise was that Leaderboards sits too low for the browser to scroll that far;
   it does not.

   ❌ **A TRAILING SPACER WAS BUILT, MEASURED AND REMOVED.** 70vh of `::after` room took the
   one unreachable heading from 766px short to 136px, and ~85vh would have closed it — but
   **that heading is Poll movement, which carries NO anchor**, so the only thing the spacer
   bought was two-thirds of a blank screen at the foot of every page on the site.
   ⚠️ A215 RENAMED THAT HEADING TO **Tracking Top 25 Changes** AND MOVED IT SECOND IN the
   Looking Back tab. The measurement above is left as it was taken — it is dated, and a
   rewritten measurement is worse than an accurate one — but the heading it calls "Poll
   movement" is the one now called Tracking Top 25 Changes, and **it still carries no
   anchor**, which is the claim this paragraph is actually making. Measuring
   before shipping is the whole point; this is what it looked like when it paid.

   ✅ SO WHAT SHIPS IS THE HALF THAT COSTS NOTHING. `scroll-margin-top` keeps the heading from
   landing flush against the viewport edge, which reads as clipped rather than as placed, and
   it is inert on every page that never receives a fragment. */
[id] { scroll-margin-top: .75rem; }

/* 🚨 A189 (cfdb-main-R-1932). A RANK GUTTER, THEN THE THREE CATEGORY COLUMNS.
   Marc: "have a row header with the rank so it's only printed once per row instead printing
   in each card." The board is rows now — the gutter is the first grid track and each card
   row writes one rank cell followed by three cards, so the number is drawn once. */
.cfdb-cardboard { display:grid;
                  grid-template-columns:1.5rem repeat(3, minmax(0, 1fr));
                  gap:.5rem 2rem; margin:.25rem 0 .75rem; align-items:start; }
/* The rank, once per row. Tabular figures so 1 and 10 occupy the same width and the gutter
   stays a gutter. Top-aligned with the cards beside it rather than centered on a tall row. */
.cfdb-cardrow-rank { font-size:.72rem; font-weight:700; opacity:.45;
                     font-variant-numeric:tabular-nums; text-align:right;
                     padding-top:.55rem; }
.cfdb-cardrow-head { padding-top:0; }
/* A178: "Add decent amount of horizontal spacing between the player cards" — the gap is on
   the BOARD (between the three columns) rather than on the card, because that is the
   horizontal space he is pointing at; a card's own margin would only indent it. */
.cfdb-cardcol { min-width:0; display:flex; flex-direction:column; gap:.3rem; }
/* 🚨 A212 (cfdb-main-R-2523). THE SUB-HEADER SITS IN THE HIERARCHY INSTEAD OF UNDER IT.
   > **MARC, v14:** *"The sub-headers (QB, Receiving, etc) - need to be bigger fonts and look
   > like a sub-header."*
   📊 MEASURED, ALL THREE LEVELS TOGETHER, because a sub-header that out-ranks its own section
   is worse than one that is too small:
       section heading (h3)   28px / 600
       board label (bold)     16px / 600
       sub-header BEFORE    11.52px / 700   <- smaller than the body text around it
       sub-header AFTER      13.6px / 700
   ✅ 13.6px is clearly a heading against the 11.52px it replaces and stays **2.4px under the
   board label** and 14.4px under the section heading, so the three still read top to bottom.
   ⚠️ AND THE OPACITY LIFTS WITH THE SIZE. At .6 a bigger label is a bigger gray smudge; the
   rule is a heading now, so it takes the page's own ink. */
.cfdb-cardcol-head { font-size:.85rem; font-weight:700; letter-spacing:.04em;
                     text-transform:uppercase; opacity:.85; padding-bottom:.22rem;
                     border-bottom:1px solid var(--cfdb-edge); }
/* A212 (cfdb-main-R-2524): the metric names, hoisted out of the cells and onto the header
   they belong to. Lighter than the category name beside them — the category is what the
   column IS, the metrics are what its numbers MEAN. */
/* 🚨 A221 (cfdb-main-R-2687). THE SUB-HEADER'S NAMES SIT IN THE SAME CELLS AS THE VALUES, at
   the same widths, so each name is over its own column by construction. A name wider than its
   column WRAPS AT A SPACE — `PASS` over `YDS` — and never inside a word (A218's rule, which
   `overflow-wrap:normal` on the table cells enforces site-wide and is restated here because
   this element is not a table cell). ⚠️ That costs ~11px ONCE per board; letting the name set
   the column width instead cost a second band on every one of thirty cards. */
.cfdb-cardcol-head .cfdb-cardcol-metrics { display:flex; gap:.3rem;
    justify-content:flex-end; align-items:flex-end;
    font-weight:600; opacity:.65; letter-spacing:.02em; margin-left:.4rem; }
/* ⚠️ THE HEADING CELL CARRIES THE SAME 1.05rem SO ITS WIDTH MATCHES THE COLUMN BELOW IT,
   and the NAME inside is scaled down instead. Sizing the cell at the heading's own font would
   make `3ch` a different number of pixels here than in the card — the two would stop lining
   up, which is the whole thing this shares cells to achieve. */
.cfdb-cardcol-head .cfdb-cardcol-metrics .cfdb-card-metric { display:block;
    text-align:right; font-size:1.05rem; line-height:0; }
.cfdb-cardcol-head .cfdb-cardcol-metrics .cfdb-cardcol-name { display:block;
    font-size:.62rem; line-height:1.1; white-space:normal; overflow-wrap:normal; }
/* The card itself. A rule on one side rather than a box on four: thirty boxes on a page is a
   grid of borders competing with the text inside them, and the reader is scanning a ranked
   list down a column. */
/* 🚨 A175 (cfdb-main-R-1755). THE BORDER AND THE SEPARATION MARC ASKED FOR, AND THE COLOR
   QUESTION IS CLOSED RATHER THAN BLOCKED.

   > **MARC, v09:** *"I like the format on Matchup better. Needs a border, don't necessary need
   > the color on this page, but need the seperation between the other cards."*

   ✅ **HE HAS CLOSED A166's BLOCKED ITEM HIMSELF.** `_player_card`'s docstring records that
   `srv_player_game_log` publishes NO color column, so the team accent could not be drawn and
   `_accent` was not promoted (cfdb-main-R-1309). **He does not want it here** — so that is
   DECIDED, not blocked, and no model change is owed for it.

   ✅ WHAT HE WANTS IS THE SEPARATION THE COLOR WAS CARRYING. A full border on all four sides
   rather than the single left rule, and real space between cards — the proportions are
   Matchup's `.cfdb-card`, read and not imported (`matchup.py` is session B's).

   ⚠️ THE LEFT RULE STAYS THICKER THAN THE OTHER THREE. It is what gives a scanned column its
   left edge, and dropping to a uniform hairline made the grid read as a table of boxes in a
   4x zoom rather than as a stack of cards. */
/* ── A178 (cfdb-main-R-1856): THE v10 CARD IS ONE ROW, LEFT TO RIGHT ──────────────────────
   > MARC, v10: "move the team name and logo to the far left, Jersey #, Player Name, Class/Pos
   > … Move the metrics to the right side of the cards and have them more densely populated.
   > The metrics should align up/down across all cards in the column. Add a column on the far
   > left that indicates the overall rank of the player card."

   🚨 "ALIGN UP/DOWN ACROSS ALL CARDS" IS THE HARD ONE AND IT IS WHY THIS IS A GRID AND NOT A
   FLEX ROW. Cards are independent boxes: under flex, every card sizes its own columns, so a
   long team name in card 3 moves that card's metrics and nothing else — which is exactly the
   misalignment he is asking to remove. `grid-template-columns` with FIXED tracks makes every
   card lay its four cells on the same four x-positions by construction, whatever is in them.
   ⚠️ The measurement in A178's report is the evidence: maximum deviation in pixels, target 0.

   ⚠️ THE MIDDLE TRACK IS THE ONLY FLEXIBLE ONE (`minmax(0, 1fr)`), so a long player name
   ellipsises INSIDE its own cell instead of pushing the metrics out of line. `min-width:0` is
   what makes that possible at all (the R-745 class). */
/* 🚨 A189 (cfdb-main-R-1933). THE TEAM STACKS: LOGO OVER NAME.
   Marc: "Need to move the Team Name to be under the Logo b/c the card is too crowded
   horizontally to present well." The team cell keeps `_team_identity`'s markup — the same
   cell every other panel draws — and only its AXIS changes here, so nothing about what the
   cell contains moves. The column narrows from 5.75rem to 3.6rem, which is the horizontal
   space the stack buys back. */
/* 🚨 A191 (cfdb-main-R-2004). THE A189 RULE ABOVE SELECTED THE WRONG ELEMENT AND DID
   NOTHING, AND THE RENDER SAID SO: the team cell measured 58x28 with
   `flex-direction: row` — the name still beside the logo and clipped to ~5 characters.

   📊 THE MARKUP, READ OFF THE LIVE RENDER RATHER THAN ASSUMED:

       div.cfdb-card-team > span.cfdb-identity > a.cfdb-teamlink > [ .cfdb-logo-box,
                                                                    .cfdb-rank?,
                                                                    span.cfdb-team ]

   `> a` matched nothing (the anchor is a GRANDCHILD) and `> span` matched `.cfdb-identity`,
   whose only child is that anchor — so the column axis was applied to a one-item flex box,
   which is a no-op. **The logo and the name are siblings inside `.cfdb-teamlink`, and that
   is the box whose axis had to change.** The rule was written against `_team_identity`'s
   description of the cell instead of against the cell (§2.2.1c.2's class, in CSS).

   ⚠️ BOTH LEVELS ARE NAMED BECAUSE BOTH SHAPES OCCUR. `_team_identity` only wraps in an
   anchor when `table.team_link` yields an href; a team with no slug renders logo, badge and
   name directly inside `.cfdb-identity`. Selecting one of the two would stack most cards and
   silently leave the others in a row.

   ⚠️ AND IT WRAPS RATHER THAN STACKING, WHICH IS NOT THE SAME THING. A plain
   `flex-direction:column` puts the rank badge on a line of its own between the logo and the
   name — three rows for two facts. `flex-wrap` with the name at `flex:0 0 100%` keeps the
   logo and its badge together on the first line and forces only the name down, which is what
   Marc asked for: *"move the Team Name to be under the Logo"*. */
.cfdb-card-team .cfdb-identity,
.cfdb-card-team .cfdb-teamlink { display:flex; flex-wrap:wrap; justify-content:center;
                                 align-items:center; row-gap:.1rem; column-gap:.2rem;
                                 text-align:center; line-height:1.15; }
/* 🚨 A221 (cfdb-main-R-2689). THE RANK MOVES DOWN BESIDE THE ABBREVIATION.
   > **MARC:** *"For the Team Rank, look at the attachment, bottom-left for Tex. That's where
   > the Rank should be… we have enough white space in the middle to give a little room for
   > Rank and Team Abbr."*
       was      line 1  [logo] #1        after   line 1  [logo]
                line 2  TEX                      line 2  #1 TEX
   ✅ THE LOGO TAKES THE WHOLE FIRST LINE, so the badge wraps with the name instead of riding
   beside the disc; the name stops claiming 100% so the two can share their line.
   🚨 AN UNRANKED CARD IS UNCHANGED BY CONSTRUCTION — logo on line 1, abbreviation on line 2,
   which is exactly the two bands it already had. 138 of 150 cards are unranked and none of
   them moves (AC-G.28's principle, measured rather than asserted). */
/* 🚨 A223 (cfdb-main-R-2626). THE LINE BREAK MOVED OFF THE PAINTED BOX.
   A221 put `flex:0 0 100%` on `.cfdb-logo-box` to make the logo claim the first line. The
   LAYOUT was right — rank on the abbreviation's line, 8 of 8 ranked, unranked unmoved — and
   the target was wrong: **`.cfdb-logo-box` is the painted element.** It carries
   `border-radius:50%` and a gray background from its base rule while the `<img>` keeps its own
   18px inline size, so the disc stretched into a pill with the mark at its left edge.
   📊 MEASURED ON ALL 150 CARDS BEFORE THIS FIX: painted box 41.66..57.59 wide x 18 tall —
   **square on 0 of 150.** It is visible in A221's own after-crop, which was taken and not read.

   ✅ A ZERO-HEIGHT PSEUDO-ELEMENT CLAIMS THE LINE INSTEAD, ordered between the logo and the
   badge. Nothing painted is resized: the box goes back to its natural 18x18 and the break
   happens after it.
   ⚠️ BOTH CONTAINERS, because both shapes occur (A191): `_team_identity` wraps in an anchor
   only when the row has a slug, so a team without one renders the logo directly inside
   `.cfdb-identity`. A rule naming one of the two fixes most cards and leaves the rest.
   ⚠️ AND `order` IS SET ON EVERY ITEM, not just the break. An item with no `order` defaults to
   0 and would sort BEFORE the pseudo-element whatever the source order says. */
.cfdb-card-team .cfdb-identity::before,
.cfdb-card-team .cfdb-teamlink::before { content:''; order:2; flex:0 0 100%; height:0; }
.cfdb-card-team .cfdb-logo-box,
.cfdb-card-team .cfdb-monogram-empty { order:1; }
.cfdb-card-team .cfdb-rank { order:3; }
.cfdb-card-team .cfdb-team { order:4; flex:0 1 auto; font-size:.68rem; }

.cfdb-card { min-width:0; padding:.4rem .45rem; border:1px solid var(--cfdb-edge);
             border-left:2px solid var(--cfdb-edge);
             background:var(--cfdb-row-alt, transparent); border-radius:3px;
             margin-bottom:.4rem;
             align-items:center; gap:.4rem;
             /* 🚨 A213 (cfdb-main-R-2544). THE TRANSITION IS DECLARED HERE AND THE DELAY IS
                DECLARED ON THE HOVER RULE, WHICH IS WHAT MAKES THE HIGHLIGHT ASYMMETRIC.
                `today._player_card_grid` emits, per player who appears on more than one board
                in a group, a `:has()` rule carrying `transition-delay:400ms`. Coming OFF the
                hover that rule stops applying, so this 0ms delay governs and the highlight
                releases immediately. **400ms on and 0ms off reads as intent; 400ms both ways
                reads as lag.** No script is involved — Streamlit strips handlers (R-121). */
             transition:background .18s ease, border-left-color .18s ease;
             transition-delay:0ms;
/* 🚨 A192 (cfdb-main-R-2013). A FLEX ROW THAT WRAPS, NOT A THREE-TRACK GRID — AND THE TWO
   FIXED TRACKS GIVE BACK THE WIDTH THEY WERE NEVER USING.

   > **MARC, v11:** *"the card is too crowded horizontally to present well."*

   📊 MEASURED IN CHROMIUM ON THE REAL PAGE, 2026 week 3, SIDEBAR OPEN. The grid this
   replaces was `3.6rem minmax(0,1fr) 7.25rem`, and both fixed tracks were oversized:

       team track      slot 57.6px   widest content 28.3px   (a 28px logo over a 4-char name)
       metrics track   slot 116px    widest content 66.6px

   **115.6px of every card was reserved and unused**, while the name — the one thing a player
   card exists to say — got what was left:

       1100px   card 173.3   name slot 0       30 of 30 cards overflowing
       1280px   card 233.3   name slot 29.6   150 of 150 overflowing
       1440px   card 286.7   name slot 82.9    67 of 150 overflowing
       1680px   card 366.7   name slot 162.9    0 overflowing

   🚨 AT 1100 THE THREE TRACKS SUMMED TO 186.4px INSIDE A 173.3px CARD, so the middle one
   resolved to ZERO and the name painted on top of the metrics. No redistribution inside the
   name block could have fixed that: the card was overcommitted before the name was reached.

   ✅ THE RULE THIS ENFORCES: **the last name is never truncated at any width from 1100 up.**
   `--cfdb-card-name-min` is the widest real last name plus the jersey and its gap, so the
   name block can never be squeezed below it — and because the card WRAPS rather than
   shrinks, the metrics (then the team) drop to a second line instead of eating the name.

   ⚠️ WRAP RATHER THAN A MEDIA QUERY, AND THAT IS THE POINT. The board's width depends on
   whether Streamlit's sidebar is open, which a viewport media query cannot see — the same
   1100px viewport is a 640px board with it open and ~885px without. A flex container
   reflows on its OWN width, so both cases are right with no breakpoint to maintain.

   ⚠️ AND IT IS WHY THE BOARD STILL HAS THREE COLUMNS. A192's brief offered "3 → 2 columns
   below a measured breakpoint" as the last resort; reclaiming the 115.6px made it
   unnecessary, and the rank gutter, the three category headings and their alignment all stay
   exactly as A189 left them. */
             display:flex; flex-wrap:wrap; }
.cfdb-card > .cfdb-card-team { flex:0 0 var(--cfdb-card-team-w); }
.cfdb-card > .cfdb-card-who  { flex:1 1 var(--cfdb-card-name-min);
                               min-width:var(--cfdb-card-name-min); }
.cfdb-card > .cfdb-card-stat,
.cfdb-card > .cfdb-card-metrics { flex:0 0 auto; margin-left:auto; }
/* 🚨 A221 (cfdb-main-R-2687). `min-width:max-content` IS GONE, AND IT WAS THE RAGGED EDGE.
   📊 Measured at 1440 before the change (`ci/measure_card_budget.py`): sizing each cell to
   its own content gave a column's ten values up to FIVE different left edges — Touchdowns QB
   spanned 14.44px, Receiving 17.74px. **`today._metric_widths` now sets one width per column
   from the rendered ten**, so every card in a column emits the same total metrics width and
   `margin-left:auto` puts them all at the same x. The alignment is a consequence of the
   widths, not of a second positioning rule — which is what lets the block stay pinned right
   and `who` stay able to shrink at 1024.
   ⚠️ A192's note below is why `flex:1 1 0` was wrong too: equal thirds wrapped `483` under
   its own label. Neither equal thirds nor content-sizing; a measured width per column. */
.cfdb-card .cfdb-card-metric { flex:0 0 auto; }
/* ⚠️ THE LAST NAME OPTS OUT OF THE ELLIPSIS `player_row` PUTS ON EVERY LINE. That clip is
   right for Matchup and for the FIRST name here; on this card the surname is the thing the
   min-width above exists to protect, so clipping it would quietly undo the whole rule. */
/* 🚨 A192 (cfdb-main-R-2015). `!important`, AND IT IS THE CANONICAL CASE FOR IT RATHER THAN
   A SHORTCUT: these two declarations have to beat an INLINE `style=`, which outranks every
   class selector no matter how specific.

   `identity.player_row` writes `min-width:0;white-space:nowrap;overflow:hidden;
   text-overflow:ellipsis` into the attribute of all three name elements. ⚠️ **A192's first
   attempt at both rules was silently inert** — `min-width:7rem` and `overflow:visible` were
   written, were correct, and lost to the attribute; one surname ("Sagapolutele") was still
   being cut with the rule sitting in the sheet.

   ✅ MOVING THE FOUR DECLARATIONS INTO A CLASS RULE IS THE TIDIER CSS AND WAS TRIED FIRST.
   It was reverted because `tests/test_matchup_postgame.py` and `tests/test_matchup_yardage.py`
   locate this markup by those literal strings, and those are **session B's files** — a
   shared-module change that forces edits into the other session's tests is R-729's shape
   exactly. Two `!important`s in Today's own sheet cost less than crossing that line, and
   leave Matchup's markup byte-identical to what its tests assert.

   ⚠️ SCOPED UNDER `.cfdb-card`, which `matchup.py` does not use anywhere — asserted by
   `test_matchup_cannot_be_reached_by_todays_card_rules`. */
.cfdb-card .cfdb-player-last { overflow:visible !important; text-overflow:clip !important; }
/* The jersey rides above the name rather than stealing from it once the card is narrow
   enough that the two cannot share a line — see `--cfdb-card-name-min` for the measurement. */
.cfdb-card .cfdb-player-row  { flex-wrap:wrap; }
/* 🚨 A221 (cfdb-main-R-2690). THE JERSEY TAKES ITS OWN LINE ON EVERY CARD.
   📊 MEASURED BEFORE: on the yardage board it sat BESIDE the name on 16 of 30 cards and ABOVE
   it on 14, and cards in one row differed in height by 45% (47.97px against 69.38px).
   **The driver was never the name — it was the metrics block.** `.cfdb-card .cfdb-player-row`
   wraps, so the jersey shared the name's line only when `who` happened to be wider than
   25.6 + 6.4 + the name's floor, and `who` was whatever the content-sized metrics left over.
   ⚠️ FIXING THE COLUMNS MADE `who` CONSTANT PER BOARD BUT NOT ACROSS BOARDS — re-measured at
   that point: yardage 0 beside / 30 above, Touchdowns 0 / 30, **Defense 10 / 20**. Still two
   places, now for a subtler reason.
   ✅ `flex:0 0 100%` REMOVES THE THRESHOLD INSTEAD OF MOVING IT. One place on every card, at
   every width, whatever the metrics do next — and a card whose player has no jersey draws the
   same em-dash line, so its footprint is unchanged (the screenshot's CNSU row).
   1.6rem clears the widest drawn jersey of 25.5px and stays as the minimum. */
.cfdb-card .cfdb-player-jersey { min-width:1.6rem; flex:0 0 100%; }
.cfdb-card .cfdb-player-name { min-width:var(--cfdb-card-name-min) !important; }
/* A192: class and position move to the cell's `title` — see `today._player_card` for why,
   and note this cannot reach Matchup, which uses no `.cfdb-card`. */
.cfdb-card .cfdb-player-meta { display:none; }
/* The rank Marc asked for, far left. Tabular figures so 1 and 10 occupy the same width and
   the column below stays a column. */
.cfdb-card-rank { font-size:.72rem; font-weight:700; opacity:.45;
                  font-variant-numeric:tabular-nums; text-align:right; }

/* 🚨 A178: THE TEAM NAME IN THE TEAM'S COLOR, WITH THE UNDERLINE KEPT — Marc's own
   constraint, and a real one: color alone is not an affordance, and a colored-but-unstyled
   name reads as emphasis rather than as a link. Both declarations live in one rule so
   neither can be dropped without the other.
   ⚠️ THE VALUE ARRIVES AS A `light-dark()` PAIR FROM `identity.accent_color`, set on the
   wrapper as a custom property by the page. The BROWSER resolves it, so a mid-session theme
   flip is correct with no Python in the loop — and the pair is the CONTRAST-SAFE one, not the
   raw brand color, which is what stops a #000000 team vanishing on the dark page (B109). */
.cfdb-card-team a { color:var(--cfdb-card-accent, inherit); text-decoration:underline;
                    text-underline-offset:2px; }

/* A175: three metrics on one line, sharing the width evenly so the eye can compare down a
   column. ⚠️ `min-width:0` on the children, or a long value stops the flex row shrinking and
   the third metric falls off the card. */
/* A175: the player identity and the team share ONE line — Marc: "There is a lot of horizontal
   space in this layout, can we fit team info on an existing line?" The who grows, the team
   takes what it needs, and `min-width:0` on both lets long names ellipsise instead of pushing
   the team off the card. */
/* A175's head row is retained for any caller still drawing the stacked card; A178's grid
   supersedes it on the Today boards. */
.cfdb-card-head { display:flex; align-items:center; justify-content:space-between;
                  gap:.6rem; min-width:0; }
.cfdb-card-head-who { min-width:0; flex:1 1 auto; }
.cfdb-card-head .cfdb-card-team { flex:0 1 auto; min-width:0; margin-top:0; }

/* A178: "more densely populated" — the gap halves and the vertical margin goes, because the
   metrics now sit in their own grid track rather than on a line of their own. */
/* 🚨 A212 (cfdb-main-R-2521). THE GAP WAS 4px AND THE CARD HAD ROOM TO SPARE.
   > **MARC, v14:** *"The metrics are too compressed on the right side. Spread them out, give
   > them some padding in between."*
   📊 THE CARD'S BUDGET AT 1440, MEASURED: 286.7px = 14.4 padding + 44 team + 148.5 who +
   64 metrics, and the three metrics inside that 64px were 26.6 + 13 + 16.4 with 4px between
   them. **The slack is in `who`**, which is `flex:1 1 112px` and had grown 36.5px past its
   floor — so the metrics were the only slot NOT taking its share.
   ⚠️ THE CONSTRAINT IS THE CARD, NOT STREAMLIT'S THREE COLUMNS. The board is one `grid` with
   `1fr` tracks; at 1440 each card gets 286.7px whatever this rule says. The compression was
   internal, and so is the fix.
   ✅ .6rem between metrics, and the block is allowed to claim what it needs before `who`
   grows into it. */
/* ⚠️ A221: THE GAP COMES DOWN FROM .6rem, AND IT IS A BUDGET DECISION RATHER THAN A TASTE.
   📊 The card is 286.66px at 1440 and its fixed costs are padding 14.4 + team + the name's
   floor, which leaves ~97px for three metric columns. A212 widened this gap to .6rem to
   decompress a huddle; with the cells now at measured widths the decompression is in the
   cells, and 2 x 9.6px of gap is width the numbers can use instead. `align-items:center`
   because the cells are rows now, not baseline-aligned stacks. */
/* ── A216 (cfdb-main-R-2600…R-2603): THE KPI ROW ABOVE MOST EXCITING ────────────────────
   > **MARC, v14:** *"Need a KPI summary row - above Most Exciting"*

   🚨 SEVEN TILES, THREE OF THEM CARRYING A PICTURE, ABOVE A SECTION THAT ALREADY HAS PLENTY.
   The row is a flex line inside the site's SHARED `.cfdb-scroll` wrapper (A208) rather than a
   grid that reflows: a grid would wrap tile 7 onto a second line at 1024 and turn a summary
   ROW into a summary BLOCK, which is A209/A210's defect in a new place. Scrolling keeps the
   row one row at every width and the wrapper's own note says so.

   ⚠️ `flex:0 0 auto` AND A MIN-WIDTH, NOT `flex:1`. Equal-width tiles would size every tile
   to the widest sub-line — "35 of 74 · 1 push" — and leave `FBS games` with a 12-character
   number slot for two digits. Each tile takes the room its own content needs. */
/* 📊 THE GAP AND THE FLOOR ARE MEASURED, NOT CHOSEN. The first render needed 1,174px against
   980px of content width at 1440 — so the row scrolled at the WIDEST supported viewport, and a
   summary you have to scroll is not a summary. `.cfdb-scroll` is still there and still right
   for 1024; it should not be doing the work at 1440. */
.cfdb-kpirow { display:flex; align-items:stretch; gap:.55rem; margin:.25rem 0 .1rem; }
/* 🚨 A `max-width` IS WHAT MAKES THE LABEL RULE ABOVE DO ANYTHING, AND THAT COST A RENDER.
   Removing `white-space:nowrap` from the label changed the row's total by ZERO px: a
   `flex:0 0 auto` item's base size is its MAX-CONTENT, so a wrappable label still contributes
   its full unwrapped width until something caps the box. 📊 Measured — 995.3px of tiles before
   and 995.3px after. **The cap is the fix; the wrap is what makes the cap survivable.**
   ⚠️ 11rem is the floor the widest tile actually needs: two 72px thumbnails plus their gap and
   the tile's padding is ~170px, so anything less would squeeze the pictures. */
/* 🚨 A231 (cfdb-main-R-3023). `flex:1 1 auto`, NOT `0 0 auto` — THE ROW TAKES THE WIDTH IT
   IS GIVEN.
   > MARC, v17: *"It should consume the same width as the Most Exciting table. So, has some
   > more horizontal real estate."*
   📊 MEASURED BEFORE: seven tiles summed to 864.1px inside a 980px box at 1440 and a 1140px
   box at 1600 — 116px and 276px of the row's own width left empty, while the table directly
   below it used all of both. `0 0 auto` sizes every tile to its MAX-CONTENT and then stops,
   so the row could never fill anything.
   ⚠️ THE GROW BASIS IS `auto`, NOT `0`. `flex:1 1 0` would make all seven EQUAL, which is
   wrong here: the Winning-vs-losing tile carries two 72px thumbnails and needs more room
   than "Went over" does. `auto` keeps each tile's content-derived basis and shares out the
   slack in proportion, so the row fills without flattening the differences that mean
   something.
   🚨 AND THE SHRINK FACTOR IS `0`, WHICH A MEASUREMENT DECIDED RATHER THAN A PREFERENCE.
   `flex:1 1 auto` was tried first and it fills the row correctly at 1440 and 1600 — and at
   1300 and 1024 the tiles shrink toward `min-width` and **four and five labels start
   wrapping**, which is the exact complaint this change came from. 📊 Measured: at 1300,
   `1 1 auto` wrapped Average over/under, Favorites won, Favorites covered and Undefeated but
   lost; `1 0 auto` wraps none at any of the four widths.
   ✅ SO: GROW INTO SLACK, NEVER SHRINK OUT OF IT. Where there is room the row takes it; where
   there is not, the tiles keep their content width and the row scrolls in `.cfdb-scroll` as
   it always has. `min-width` stays as the floor that was already there. */
.cfdb-kpi { flex:1 0 auto; min-width:6rem; max-width:11rem; display:flex;
            flex-direction:column;
            gap:.1rem; padding:.5rem .65rem;
            border:1px solid var(--cfdb-u2, #87878d); border-radius:6px; }
/* The label is the quietest thing in the tile and the value the loudest, because a reader
   scanning seven of these is scanning the NUMBERS and reading the labels only once. */
/* 🚨 THE LABEL WRAPS AND THE VALUE DOES NOT, WHICH IS A218's RULE APPLIED HERE: *a team name
   on two lines is a layout, a number on two lines is a lie.*
   ⚠️ AND THE LABEL WRAPS BECAUSE OF THE TILE'S `max-width`, NOT BECAUSE OF ANYTHING WRITTEN
   HERE. An earlier version set `overflow-wrap:normal` on this rule and measured the row's
   total at 995.3px BEFORE and 995.3px AFTER — a `flex:0 0 auto` item's base size is its
   max-content, so the declaration was inert. It is gone rather than left looking load-bearing
   (§3.2.3), and `tests/test_numeric_cells_never_break.py` is what refused to let it stay. */
/* ── A225 (cfdb-main-R-3051), KEPT AS HISTORY BECAUSE A231 RETIRED IT. ──────────────────
   A225 gave every label `min-height:3.2em` so that every figure started at one y.
   📊 The defect it fixed was real and measured: six numerals began at 570.0 and the seventh
   at 587.4 — 17.4 CSS px lower — because *"Undefeated teams that lost"* wrapped, and a
   wrapped label pushes its numeral down. A216 had measured the ROW (one band, 110.0px),
   which was correct and blind to it: **the row was one band and the figures inside it were
   not on one line.**
   🚨 MARC HAS SAID THIS IS WHAT HE NOTICES, about the player cards, in his own words:
   *"Why aren't they numbers vertically aligned in the same space?"* A221 answered it there.
   ⚠️ A225 CHOSE RESERVING OVER TRUNCATING, and was right to: capping the label to one line
   buys the alignment by deleting words a reader needs. **What A231 did instead was make the
   label shorter — Marc's own wording — so there is nothing left to reserve for.** The
   alignment is unchanged; only the empty second line is gone. */
/* 🚨 A231 (cfdb-main-R-3025). THE RESERVED SECOND LINE IS GONE, AND A MEASUREMENT RETIRED IT
   RATHER THAN A PREFERENCE.
   📊 A225 added `min-height:3.2em` because ONE label wrapped and pushed its numeral 17.4px
   below the other six. A231 renamed that label to Marc's own shorter wording and made the
   tiles `flex:1 0 auto`, and with both in place **no label's text wraps at 1600, 1440, 1300
   or 1024, in either scheme** — so the reserve was holding 17.4 CSS px of empty space on
   every one of the seven tiles, every render.
   ⚠️ MEASURED ON THE TEXT'S OWN LINE BOXES, NOT ON THE BOX. `ci/measure_kpi_row.py`'s
   `labelLines` divides the box height by the line height, so while this very rule existed it
   could only ever answer "2" — it reported all seven labels as wrapping when what it saw was
   the reserve. A231 added `labelTextLines`, a Range over the label's contents, which yields
   one rect per line the TEXT occupies. **The old figure would have said the reserve was
   still needed, for as long as the reserve was there.**
   🚨 AND THE PROPERTY IT PROTECTED IS NOW HELD BY A TEST INSTEAD OF BY PADDING.
   `test_no_kpi_label_is_long_enough_to_wrap` fails if any label grows past what its tile can
   hold on one line — so a future longer label goes RED rather than silently pushing one
   numeral off the shared baseline, which is what happened last time and took a render to
   find. **The reserve made the failure invisible; the test makes it loud.** */
.cfdb-kpi-label { font-size:.68rem; text-transform:uppercase; letter-spacing:.03em;
                  opacity:.7; line-height:1.6; }
/* 🚨 A231. THE NUMERAL GROWS, AND ONLY BECAUSE THE TWO CHANGES ABOVE MADE ROOM FOR IT.
   > MARC, v17: *"Once the title wordwrap is fixed, KPI font has room to grow."*
   ⚠️ THE ORDER IS THE WHOLE POINT AND IT IS HIS: the wrap had to go first, then the reserve,
   and only then is there vertical room to spend. Growing the figure with a wrapped label
   still on screen would have made the misalignment worse rather than better. */
.cfdb-kpi-value { font-size:1.7rem; font-weight:700; line-height:1.15;
                  font-variant-numeric:tabular-nums; white-space:nowrap; }
/* 🚨 THE DENOMINATOR IS ON THE FACE OF THE TILE, NOT IN A TOOLTIP. A214 publishes it for
   every rate because *"62% of favorites covered"* over 8 games and over 60 are different
   claims; a reader who has to hover to find that out has already read the wrong one. */
.cfdb-kpi-sub { font-size:.64rem; opacity:.65; line-height:1.25; white-space:nowrap; }
/* 🚨 A235 (cfdb-main-R-3029). `.cfdb-kpi-vs` AND `.cfdb-kpi-pair` ARE GONE BECAUSE THEIR TILE IS.
   `-vs` drew the en dash in `38.9–17.2` and `-pair` sat two 72px thumbnails side by side; Marc's
   v18 split that tile in two, so each score now has its own tile and its own full-width chart and
   there is no pair to lay out and no dash to space. **Dead rules are deleted rather than left
   looking load-bearing** (§3.2.3) — a selector nothing emits is a claim that something does. */
/* 🚨 AND THE PANEL LOSES ITS OWN FRAME INSIDE A TILE, WHICH IS NOT COSMETIC. `.cfdb-dist-panel`
   carries a border, a radius and .6rem of padding because it was written as a standalone
   full-page chart; inside `.cfdb-kpi`, which already has a border, that renders as a box inside a
   box and spends 24px of the 140px the chart was just given. The panel keeps its structure and
   drops its chrome. */
/* 🚨 A237 (cfdb-main-R-3042). THE FIGURE AND ITS p25/p50/p75 SHARE A ROW.
   > MARC, 2026-09-25: *"How about a tight table to the right KPI value that shows p25, p50, p75."*
   📊 IT HAD TO COST NOTHING HORIZONTALLY AND IT DOES. A235 left 22px of headroom across the whole
   row at 1440 (958 minimum against 980 given), so a table that widened seven tiles by 4px each
   would have pushed the row into a scroll at the width Marc works at. `baseline` alignment puts
   the three small rows against the numeral's own baseline, and `margin-left:auto` pushes them to
   the tile's right edge — into whitespace the 1.7rem figure was already leaving. */
/* 🚨 A239 (cfdb-main-R-3230). TOP-ALIGNED, NOT BASELINE — Marc, v19: *"Move the p25, med, p75 up
   to be aligned with the top of the KPI # and remove the wasted whitespace."*
   ⚠️ `baseline` put the FIRST stat row on the numeral's baseline, which pushed the other two
   below it and left the space above them empty. `flex-start` puts the block's top edge on the
   numeral's top edge, which is what he described and what closes the gap. */
.cfdb-kpi-head { display:flex; align-items:flex-start; gap:.3rem; min-width:0; }
/* ⚠️ THE TABLE MAY SHRINK AND THE NUMERAL MAY NOT — A218's rule, which this row has paid for
   twice: *a team name on two lines is a layout, a number on two lines is a lie.* */
/* 📊 A239: ONE INCREMENT UP — `.56rem` to `.64rem`, which is the step the row already uses
   (`.cfdb-kpi-sub` is `.64rem`) rather than a new size invented for this block. The tighter
   `line-height` is what "remove the wasted whitespace" buys: three rows now occupy less height
   than two did, so the block clears the numeral without pushing the chart down. */
.cfdb-kpi-head .cfdb-dist-stats { margin-left:auto; min-width:0; flex:0 1 auto;
    font-size:.64rem; line-height:1.12; opacity:.85; }
.cfdb-kpi-head .cfdb-dist-stat { gap:.3rem; }
/* 🚨 THE LABEL AND THE VALUE BOTH — Marc said *"p25 and p75 values and labels"*, and painting
   only the number would leave the row reading as half-related to the box. `.cfdb-iqr` is set by
   `distribution.stats_table` on exactly those two rows and on no other. */
.cfdb-dist-stat.cfdb-iqr, .cfdb-dist-stat.cfdb-iqr span, .cfdb-dist-stat.cfdb-iqr b {
    color:var(--cfdb-iqr); }
.cfdb-kpi .cfdb-dist-panel { border:0; border-radius:0; padding:0; margin:.25rem 0 0; }
/* `.cfdb-dist-body` is a flex row because the standalone panel puts the stats table beside the
   chart. The KPI tile passes `stats=False`, so there is one child and the gap would be dead
   space. ⚠️ AND THE SVG MUST NOT SHRINK: it is a FIXED width here (see `panel()` — a chart with
   axis text cannot use `preserveAspectRatio='none'` without distorting its own digits), so
   `flex:1 1 auto` would squeeze the picture narrower than the geometry it was drawn at while
   every tick label stayed where it was put. */
.cfdb-kpi .cfdb-dist-body { gap:0; }
.cfdb-kpi .cfdb-dist-body .cfdb-dist-svg { flex:0 0 auto; }
.cfdb-kpi .cfdb-dist { margin-top:.15rem; }

/* 🚨 A216 (cfdb-main-R-2604). THE BAR'S WIDTH AND THE GAP BESIDE IT ARE VARIABLES NOW,
   BECAUSE TWO FILES HAD TO AGREE ABOUT THEM AND DID NOT.
   `today._metric_widths` budgets the cell; this rule draws what goes in it. A221 wrote the
   budget as `_SPARK_SLOT_CH = 3` — three `ch` — for a bar sized `1.9rem`. 📊 MEASURED at
   1440: `ch` on this cell is ~9.33px, so three of them is 28px against a bar plus gap of
   34.4px, and **the cell was 6.4px too narrow**. The value is `flex:1 1 auto; min-width:0;
   white-space:nowrap`, so the shortfall came out of the VALUE BOX and the digits overflowed
   it — landing on the bar with `box→track` still reading a perfectly correct +4.00px.
   ⚠️ THAT IS WHY THE DEFECT SURVIVED A221's OWN MEASUREMENT: every box edge was right.
   ✅ THE FIX IS THE UNIT, NOT THE NUMBER. The cell is now
   `calc(<digits>ch + var(--cfdb-card-spark-w) + var(--cfdb-card-spark-gap))`, so the digits
   are budgeted in `ch` — correct, they are tabular — and the bar's slot in the same `rem`
   the bar is drawn in. The two cannot drift apart again because they are one value. */
.cfdb-card-metrics { display:flex; gap:var(--cfdb-card-metric-gap, .55rem);
                     align-items:center; margin:0; justify-content:flex-end;
                     --cfdb-card-spark-w:1.9rem; --cfdb-card-spark-gap:.25rem; }
/* 🚨 A221 (cfdb-main-R-2687/R-2688). THE CELL IS A ROW NOW, NOT A COLUMN.
   > **MARC:** *"sparkbar should be beside the number, not under. That's too noisy for the
   > eye to scan down."*
   The value is right-aligned inside its own fixed width — a number column is read from its
   units place — and the bar sits BESIDE it in a slot of its own. `today._metric_widths`
   writes the width; this rule decides what happens inside it. */
/* 🚨 THE `ch` UNIT RESOLVES AGAINST *THIS* ELEMENT'S FONT, AND THAT COST A RENDER.
   `today._metric_widths` writes `width:3ch` for a three-digit column. The first version left
   this cell at the card's base size while `.cfdb-card-value` was 1.05rem — **so 3ch was three
   digits of the SMALLER font and the value wrapped**: `333` drew as `33` over `3`, `454` as
   `45` over `4`. 📊 Caught in the after-crop, which is what the crop is for; the numbers on
   the page contradicted a measurement that said every column was one left edge wide.
   ✅ THE CELL CARRIES THE VALUE'S OWN SIZE, so `ch` means a digit of the text it is sizing. */
/* ⚠️ THE GAP IS THE VARIABLE THE WIDTH BUDGET ALSO READS (A216). A literal here would be a
   second copy of a number `_metric_widths` has to know, which is the drift just fixed. */
.cfdb-card-metric { display:flex; flex-direction:row; align-items:center; min-width:0;
                    flex:0 0 auto; gap:var(--cfdb-card-spark-gap, .25rem);
                    justify-content:flex-end; font-size:1.05rem; }
/* 🚨 THE VALUE FILLS ITS CELL AND RIGHT-ALIGNS ITS TEXT, WHICH IS NOT THE SAME AS
   RIGHT-ALIGNING THE VALUE — and the difference is the whole measurement.
   📊 The first version made the value `flex:0 0 auto; margin-left:auto`. The digits lined up
   on their units place correctly, and **the element's LEFT edge then varied with the digit
   count**: `ci/measure_card_budget.py` still reported 5 distinct left edges on Touchdowns QB.
   ⚠️ A right-aligned box of varying width cannot share a left edge — so the box is made
   constant and the TEXT is aligned inside it. One left edge, one right edge, units place
   under units place. */
.cfdb-card-metric .cfdb-card-value { flex:1 1 auto; min-width:0; text-align:right; }
/* ⚠️ NO `font-size` HERE — IT INHERITS THE CELL'S, which is what makes `ch` mean the same
   thing to the width and to the glyphs. 🚨 AND `white-space:nowrap`, for A217's reason in its
   own words: *a team name on two lines is a layout, a number on two lines is a lie.* A column
   sized at exactly its digit count has no slack for a rounding error; this makes the failure
   an invisible overflow into measured white space rather than a broken figure. */
.cfdb-card-metric .cfdb-card-value { font-weight:700; line-height:1.15; white-space:nowrap; }
/* 🚨 A212 (cfdb-main-R-2522). A SPARK UNDER THE PRIMARY METRIC, SCALED ACROSS ITS OWN COLUMN.
   > **MARC, v14:** *"Can we add a small sparkbark to help give a quick visual reference to the
   > variance in the metric up/down the leaderboard."*
   ⚠️ THE RULE IS REUSED, NOT THE MARKUP — which is exactly what A203 did and said why. The
   shared `.cfdb-spark` OVERLAYS a right-aligned value on a left-anchored bar; a card's metric
   is a stacked value-over-label only ~27px wide, so an overlay would put the number on the
   bar. What is reused is `_spark_max`'s rule: **one denominator per column, over the rows
   shown, with `_SPARK_HEADROOM`** — the same function, called per card column.
   ⚠️ §4.2.1 IS NOT ENGAGED, for `_spark_cell`'s own reason: a bar's width is a rendering
   proportion of one published number against another in the SAME frame. No new column, no
   page-side metric.
   ⚠️ AND THE TRACK IS DRAWN EVEN WHEN THE BAR IS NOT, so a missing value reads as an empty
   scale rather than as a missing element (AC-G.11). */
/* 🚨 A221: BESIDE THE NUMBER, IN A SLOT OF ITS OWN. It no longer inherits the value's
   width — which was ~45px under a three-digit yardage and ~18px under a one-digit `TD`, so
   one proportion drew two different pictures. Taller than 3px because a horizontal bar beside
   a 1.05rem number has the height to be read; `margin-top` is gone with the stacking. */
.cfdb-card-spark { display:block; flex:0 0 auto; width:var(--cfdb-card-spark-w, 1.9rem);
    height:6px; border-radius:3px;
    background:color-mix(in srgb, currentColor 12%, transparent); overflow:hidden; }
.cfdb-card-spark > i { display:block; height:100%; border-radius:2px;
    background:color-mix(in srgb, currentColor 42%, transparent); }

.cfdb-card-metric .cfdb-card-unit { font-size:.68rem; opacity:.6; text-transform:uppercase;
                                    letter-spacing:.02em; }
/* 🚨 A166 (cfdb-main-R-1307). THE POSITION FOLLOWS THE NAME IN A CARD, AND THIS IS R-855's
   TRAP CAUGHT IN THE ACT: read the existing path, then TEST IT FOR THE CASE AT HAND.

   `.cfdb-player` is `justify-content:space-between` — two ends — which is exactly right for the
   table cell Marc specified in Today v01: *"[Jersey #, Name, Year (left aligned)], Position
   (right aligned within the Player cell)"*. A table cell is narrow. **A card column is 390px.**

   📊 MEASURED IN THE RASTER, first card of the first board: the position sat **215.8px from its
   own player's name and 24.0px from the NEXT COLUMN's cards** — nine times closer to a
   different player than to its own. ⚠️ **Every glyph was correct and the card still said
   something false about which player it described.**

   ✅ Grouped: 7.2px from the name it belongs to, 232.7px of clear space before the next column.
   **The rule that was right in a cell is wrong in a card, and the card is where it is overridden
   — `.cfdb-player` itself is untouched.** */
.cfdb-card .cfdb-player { justify-content:flex-start; gap:.45rem; }
.cfdb-card-who { min-width:0; }
/* 🚨 THE STAT IS THE REASON THE CARD IS ON THE BOARD, so it reads second — straight after the
   name — and it is the only thing on the card set in the row's own size. */
.cfdb-card-stat { display:flex; align-items:baseline; gap:.35rem; line-height:1.15; }
.cfdb-card-value { font-weight:700; font-variant-numeric:tabular-nums; }
.cfdb-card-unit { font-size:.72rem; opacity:.6; }
/* A178: the team rides a FIXED track now, so it must clip inside it rather than push the
   player out. Without `overflow:hidden` a long name ("Florida International") widens the
   cell and the name beside it loses the space — which is what the first render showed. */
.cfdb-card-team { min-width:0; font-size:.72rem; opacity:.85;
                  overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
/* ⚠️ THE ELLIPSIS HAS TO BE ON THE ELEMENT THAT ACTUALLY OVERFLOWS. The rule above clips the
   WRAPPER; the name lives in an inner span, so without this a long team name was cut mid-glyph
   ("Texas Sta") rather than ellipsised ("Texas Sta…") — which reads as a rendering fault
   instead of as a deliberate truncation. Only the render showed the difference. */
.cfdb-card-team .cfdb-team { min-width:0; overflow:hidden; white-space:nowrap;
                             text-overflow:ellipsis; }
/* ⚠️ THE TEAM LINE REUSES `.cfdb-identity`, so the logo, the rank badge and the record all
   arrive with the treatment they have everywhere else — including A165's center alignment.
   Only the logo is resized, because a 28px disc is a table-row affordance and this is a card.

   🚨 A213 (cfdb-main-R-2545). THE WIDTH RULE THAT USED TO BE HERE IS DELETED, NOT MOVED, AND
   THAT IS THE POINT. It read `.cfdb-card-team .cfdb-logo-box, .cfdb-card-team .cfdb-logo
   { width:18px; height:18px; }` and it had NEVER APPLIED: `identity.logo_or_monogram` writes
   the size as an inline style on the element, and an inline style beats every selector short
   of `!important`. A212 read this rule, saw a 28px disc, and recorded it as a specificity
   problem — **it was never in the contest.** The size is now passed to the producer
   (`today._CARD_LOGO_PX` -> `_team_identity` -> `table.team_cell`), so a rule restating it
   here would be a second source of truth that agrees today and drifts tomorrow (§3.2.3).

   ✅ WHAT STAYS IS THE PART CSS ALONE CAN DO: the two margins that the inline style cannot
   carry. Both are written for the inline table-row context, where there is no flex gap to
   space the items; inside the card `.cfdb-identity`'s own `column-gap:.2rem` already does it,
   so they double-count and push the badge onto a third line.

   📊 MEASURED ON `#3ND`, first band against a 44px track:
       28 + 6.4 (logo m-r) + 3.2 (gap) + 4.8 (rank m-l) + 12.17 (badge) = 54.57  — wraps
       18 + 6.4              + 3.2      + 4.8            + 12.17        = 44.57  — still wraps
       18 + 0                + 3.2      + 0              + 18.25 (`#20`) = 39.45  — fits
   **A two-digit badge is why both margins go and not just one.**

   🚨 `.cfdb-monogram-empty` IS NAMED BESIDE `.cfdb-logo-box` BECAUSE IT IS A DIFFERENT CLASS
   CARRYING THE SAME 6.4px MARGIN (line 951). A team with no logo renders that branch, so a
   reset that named only `.cfdb-logo-box` would give the two branches different footprints —
   which is exactly what AC-G.28 promises they never have. 📊 Zero cards on this week's boards
   take that branch, so it is unobservable today and would surface on some future Saturday. */
.cfdb-card-team .cfdb-logo-box, .cfdb-card-team .cfdb-monogram-empty { margin-right:0; }
.cfdb-card-team .cfdb-rank { margin-left:0; }
.cfdb-card-none { font-size:.78rem; opacity:.6; padding:.3rem .5rem; }
/* A189 (cfdb-main-R-1931). The Week average row on the yardage board: a BENCHMARK, not a
   competitor. Italic and dimmed so it reads as a different kind of row at a glance, and it
   carries no logo, rank badge or record — see `today._team_yardage`'s Team column. */
.cfdb-summary-row { font-style:italic; opacity:.75; font-weight:600; }

.cfdb-team-record { font-size:.75rem; font-weight:400; opacity:.65; margin-left:.4rem;
                    white-space:nowrap; }
/* R-027: weather is a glyph plus a temperature, or a dome glyph alone. */
/* R-130: no font-size — it is a data cell and reads at the row's size like the rest. */
.cfdb-wx { white-space:nowrap; }
/* R-110: THE BROWSER DECIDES HOW MANY CARDS FIT, NOT THE SERVER.
   Streamlit renders server-side and cannot measure a viewport, so `st.columns(2)` would be a
   FIXED two-up that keeps two cards side by side on a phone. `auto-fit` + `minmax` costs no
   JavaScript and no custom component, and reflows to one column on its own.

   580px: 560 plus the 1rem MIDDLE_TRACK gained for the line block's padding. R-114 deleted
   the box score's row-label column (the team row IS the label now) and moved the kickoff
   out of a left gutter into row 1, so the card genuinely needs less than it did.
   Measured content: teams 235 + numerics 13.7rem/219 + padding 48 + gap 14.

   auto-FILL, NOT auto-FIT, AND THE DIFFERENCE IS VISIBLE ON EVERY MIDWEEK DAY. `auto-fit`
   COLLAPSES tracks it cannot fill, so a Sunday with one game rendered that card at 1460px
   while every other day rendered 723px — measured, not guessed. `auto-fill` keeps the empty
   track, so a lone card is the same size as a card with a neighbor and the page stops
   changing shape according to how many games were played. */
.cfdb-cardgrid { display:grid; gap:.7rem .9rem; align-items:stretch;
                 grid-template-columns:repeat(auto-fill, minmax(580px, 1fr)); }
.cfdb-gamecard { display:flex; flex-direction:column; height:100%;
                 padding:.55rem .7rem; border:1px solid var(--cfdb-edge);
                 border-radius:6px; }

/* R-114: ONE GRID, NOT TWO BLOCKS THAT AGREE.
   Marc's diagnosis, exactly right: the box score has a header row the teams block does not,
   so its two rows sat one header-height low, forever. It was a flex row of three independent
   children and no amount of font tuning fixes that.

   Three rows that mean the same thing on both sides:
       row 1   kickoff time             |  1  2  3  4  (OT)  T
       row 2   away logo, name, record  |  away quarters, total
       row 3   home logo, name, record  |  home quarters, total

   The team cluster and the numeric cells are cells of the SAME grid, so they share ROW
   TRACKS. Alignment survives a font change, a long name, a missing logo and a two-up reflow
   because it is geometry rather than coincidence — which is also why R-115 can keep the box
   score smaller than the team name (the track sets the baseline, not the text).

   R-015 IS NOT UNPICKED BY THIS. The page-wide `ot` fact is still decided once outside the
   day loop and still applies to every card; what changed is that the widths are grid tracks
   in rem rather than a <table>'s colgroup. That removes the failure `_ls_width` was written
   for — `table-layout:fixed` with `width:auto` still runs a content pass, which let the label
   column vary 31–46px across sixty cards — because a grid track is not negotiable. */
.cfdb-gc { display:grid; align-items:center; column-gap:0; row-gap:.1rem; }
.cfdb-gc-time { font-size:.82rem; opacity:.7; font-variant-numeric:tabular-nums;
                white-space:nowrap; }
/* R-114's visible payoff: with the time out of the left gutter the logo starts at the
   card's edge instead of after an empty column. */
.cfdb-gc-team { display:flex; align-items:center; min-width:0; padding:.1rem 0; }
.cfdb-gc-team .cfdb-team { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* R-112: which side is home, in one character. */
.cfdb-athome { display:inline-block; width:1.5em; flex:0 0 auto; font-size:.8rem;
               opacity:.6; }
/* R-115: bigger than the .78rem it was, still below the team name. */
.cfdb-gc-h, .cfdb-gc-n, .cfdb-gc-tot { font-size:.85rem; text-align:right;
    padding:.12rem .3rem; font-variant-numeric:tabular-nums; }
.cfdb-gc-h { font-size:.72rem; opacity:.55; font-weight:600; }
.cfdb-gc-tot { font-weight:700; }
/* R-116: the track is reserved on every card; the BORDERS are what make a column visible.
   A regulation game gets the cell and none of these classes, so the reader sees an OT column
   only on a game that had one and every box score still starts and ends at the same x. */
.cfdb-gc-b   { border-right:1px solid rgba(127,127,127,.30);
               border-bottom:1px solid rgba(127,127,127,.30); }
.cfdb-gc-bl  { border-left:1px solid rgba(127,127,127,.30); }
.cfdb-gc-bt  { border-top:1px solid rgba(127,127,127,.30); }
/* R-120: the marker lives INSIDE the total cell now. It had a track of its own between OT
   and T, which pushed the totals toward the card edge and meant nothing on a tie or an
   unplayed game. The spacer is what keeps the two totals aligned. */
.cfdb-winner-spacer { display:inline-block; width:.75em; }
/* R-118: the market occupies the same two row tracks as the team names, so its two lines sit
   on their baselines by construction rather than by agreement. */
/* R-134: the market is the card's ONLY content for a scheduled game and it was the smallest
   text on it. Everything here now reads at the team name's size. */
/* The preview card's line block now uses `.cfdb-gc-mid` above — one set of rules for both
   variants, so padding, dividers and weight cannot diverge between a game that has been
   played and one that has not. These classes are retained only for the legend's `Δ` sample. */
.cfdb-gc-market-move { opacity:.6; }
/* R-092: why the quarters are missing, not merely that they are. */
.cfdb-ls-why { font-size:.72rem; opacity:.6; margin-top:.15rem; text-align:right; }
/* R-015: anchored to the bottom so two cards in one grid row end level. */
.cfdb-gamecard-meta { font-size:.78rem; opacity:.7; margin-top:auto; padding-top:.35rem; }
.cfdb-gamecard-meta a { color:inherit; text-decoration:none; }
/* R-148: NO SIZE OR OPACITY OVERRIDE HERE. This block used to set 1.15rem/.7 against the
   global 1.3rem/.85, which is precisely why the glyph read as less legible in the card than in
   Inline. Inline is the reference; matching it means having no second rule, not a second rule
   tuned by eye. */
.cfdb-gamecard-meta a:hover .cfdb-details { opacity:1; }
/* R-107: a card is not a table cell, so it cannot borrow .cfdb-cell-link — that one is
   display:block, which inside a flex row would make the anchor a full-width item. */
/* R-129 REVERSES R-117, which Marc asked for one round ago and has now seen rendered.
   The record is OUT of the anchor in the card rather than styled to look non-clickable: a
   pointer cursor over dead text is worse than either state, and styling alone cannot remove
   the cursor. The color rules stay because the dense table wraps whole CELLS in an anchor,
   which it did before R-117 too, so the record still needs telling not to look like a link
   there. R-136: the underline takes the LINK color instead of the anchor's inherited one. */
.cfdb-teamlink { color:inherit !important; text-decoration:none; display:flex;
                 align-items:center; min-width:0; }
.cfdb-teamlink .cfdb-team { color:var(--cfdb-link); text-decoration-color:var(--cfdb-link); }
.cfdb-teamlink:hover .cfdb-team { text-decoration:underline; }
.cfdb-team-record { text-decoration:none !important; }
a .cfdb-team-record, .cfdb-cell-link .cfdb-team-record { color:inherit; }
/* R-136: Streamlit underlines anchors and draws the line in the ANCHOR's color, which is the
   body text here — a light rule under blue text, which fights on dark.
   `!important` because Streamlit's own `.stMarkdown a` outranks a two-class selector; measured
   without it the decoration stayed rgb(49,51,63) in light and rgb(250,250,250) in dark. */
.cfdb-table a, .cfdb-cell-link, .cfdb-teamlink .cfdb-team {
    text-decoration-color:#1f6feb !important; }
/* R-121: the monogram sits BEHIND the image, so a file that goes missing later paints the
   same gray disc a null gives instead of the browser's broken-image box. Streamlit strips
   event handlers, so `onerror` is not available here. */
.cfdb-logo-box { display:inline-block; flex:0 0 auto; vertical-align:middle;
                 border-radius:50%; background:rgba(127,127,127,.14); margin-right:.4rem; }
.cfdb-logo-box .cfdb-logo { display:block; margin-right:0; }
/* R-158 BAND 1: readiness and the as-of stamp ride the title's line, right-aligned. */
/* Slightly smaller than the body variant: at 1200 the full string needs about 380px
   and Band 1's right column offers about 320px, so it wrapped. The wrap only cost 2px
   of page height — the title is taller than two lines of this — but a status line
   broken mid-sentence reads as a fault. */
.cfdb-readiness-right { text-align:right; font-size:.74rem; white-space:normal; }
.cfdb-asof-inline { text-align:right; font-size:.78rem; opacity:.6; margin-top:.15rem; }

/* R-159. THE LEGEND, VERTICAL, IN THE SIDEBAR — where it costs zero body height and stays
   visible while the cards scroll, which is when a legend is actually consulted.
   R-161: bigger icons, sentence-case labels. */
/* In a popover, two columns (R-176) rather than one tall list. */
.cfdb-legend-side { font-size:.84rem; }
/* R-174. THE KEY BOX CENTERS ITS CONTENTS, AND A POSITIONAL MARGIN DEFEATS THAT.
   `.cfdb-neutral` carries `margin-left:.4rem` for the ROW, where the diamond trails the
   kickoff time and needs a gap (R-146). Inside a 1.6rem centerd box that same margin is .4rem
   of left padding with nothing to balance it, so the glyph sat right of center — exactly what
   Marc saw. Canceled in the legend only; it is still doing its job elsewhere. The other four
   classes are listed pre-emptively because they carry the same shape of margin and the next
   mark added to the legend would otherwise repeat this. */
.cfdb-legend-key .cfdb-neutral,
.cfdb-legend-key .cfdb-team,
.cfdb-legend-key .cfdb-rank,
.cfdb-legend-key .cfdb-winner,
.cfdb-legend-key .cfdb-ind { margin-left:0; margin-right:0; }
/* R-175: the dome inherits color and sizes with its row, like every other mark. */
.cfdb-dome { width:1.15em; height:1.15em; vertical-align:-.22em; }
.cfdb-legend-key .cfdb-dome { vertical-align:-.28em; }
/* R-177: the worked examples ride the long column's heading line. */
/* ⚠️ R-581 REMOVED `.cfdb-legend-head`, `.cfdb-legend-egs` and `.cfdb-legend-egcap`.
   They positioned the worked examples as strips right-aligned against the "Against the line"
   heading and their captions as a run-on line at the bottom of the popover — one element drawn
   in two places, which is why Marc read them as two: "the example icons are way up to the far
   right of the legend, nowhere close to the description." Examples is a section now and its
   rows use `.cfdb-legend-row` like every other entry, so the three rules had no callers left.
   Deleted rather than left: dead CSS is a justification that outlives its reason, which is the
   shape this project keeps paying for. `.cfdb-legend-eg` stays — it is the key span. */
.cfdb-legend-eg { display:inline-flex; }
/* R-580. Marc's four subsections inside "Against the line". SUBORDINATE to the section title
   deliberately: `.cfdb-legend-title` is the level Game, Result and Against the line sit at,
   and a subsection rendered at the same weight would read as a fifth section rather than a
   division of one. Lighter, smaller, not uppercase, and indented to the swatch column so the
   heading lines up with the entries it heads. */
.cfdb-legend-sub { font-weight:600; opacity:.5; font-size:.72rem; margin-top:.55rem;
                   margin-bottom:.15rem; }
/* R-622. The nested pair under the spanning "Against the line" title. Its first heading is
   already directly beneath that title, so the leading margin the sided block normally gives a
   heading would open a gap the spanned title is supposed to close. */
.cfdb-legend-nested > :first-child { margin-top:0; }
.cfdb-legend-side .cfdb-legend-title:not(:first-child) { margin-top:.9rem; }
.cfdb-legend-title { font-weight:600; opacity:.7; font-size:.78rem; letter-spacing:.03em;
                     text-transform:uppercase; margin-bottom:.5rem; }
.cfdb-legend-row { display:flex; align-items:center; gap:.55rem; padding:.16rem 0;
                   opacity:.85; }
.cfdb-legend-key { flex:0 0 1.6rem; text-align:center; font-size:1.15rem; line-height:1; }
.cfdb-legend-ch { font-size:1rem; opacity:.8; }
.cfdb-legend-note { margin-top:.9rem; padding-top:.7rem; font-size:.78rem; opacity:.7;
                    border-top:1px solid rgba(127,127,127,.18); line-height:1.5; }

/* R-166. THE STRIP RIGHT-ALIGNS IN THE KICKOFF CELL, so every card's indicators start and
   end at the same x — the team column is a page-wide track and R-141 already reserves the
   strip's width, so the alignment is geometry rather than tuning. Padding keeps them off
   R-152's divider rule at the column's right edge.
   Flex INSIDE an existing cell changes nothing about the grid; adding a cell would. */
.cfdb-gc-time { display:flex; align-items:baseline; justify-content:space-between;
                padding-right:.9rem; }

/* R-180. THE HORIZONTAL IN-BODY LEGEND'S RULES ARE DELETED, not kept "just in case".
   `.cfdb-legend` and `.cfdb-legend-strip` styled a wrapping strip under the view switch that
   R-159 replaced with a sidebar version and R-169 replaced again with the popover. Dead CSS is
   a description of a page that no longer exists, and the next person to read it has to prove
   that before they can ignore it. */

/* R-141. THE RESULT STRIP, AS CSS SHAPES RATHER THAN EMOJI.
   Marc's states mixed emoji-presentation characters with text-presentation ones. Those do not
   share a baseline, do not size together and vary by platform — and he asked the strip to
   match the kickoff time's visual size, which emoji will not do reliably. One rule here
   controls size, baseline and color for all six states; the semantics are unchanged. */
.cfdb-strip { display:inline-flex; gap:.2rem; align-items:center; vertical-align:-.08em; }
.cfdb-strip-gap { display:inline-block; width:.45rem; }
/* A164 (cfdb-main-R-1140). THE COMMENTARY CELL HAD NO RULE AT ALL AND ITS LINE BREAK WAS AN
   ACCIDENT OF COLUMN WIDTH. `_commentary` emits `<span class='cfdb-commentary'>` around the
   marks and the ESPN link and an unstyled span is INLINE, so the link fell to its own line only
   where the column happened to be too narrow to hold both. 📊 MEASURED IN CHROMIUM ON THE REAL
   PAGE, before this rule existed: Most Exciting put ESPN on its OWN line at a 1300px viewport
   (dy 23.5px) and on the SAME line at 1600px, while Biggest Upsets and Biggest Underdogs kept it
   inline at both — butted against the strip at gapX EXACTLY 0. The same markup, three different
   outcomes, decided by nothing anybody chose.

   🚨 MARC ASKED FOR TWO DIFFERENT THINGS AND THEY ARE NOT AVERAGED HERE. Today v04: a
   "carriage return" on Most Exciting, and a "Space" on the two recap panels. The measurement
   says his "Space" is a HORIZONTAL one — those panels had no gap at all — so the default is an
   inline row with a declared gap, and the stacked modifier is what Most Exciting opts into.
   ⚠️ BOTH GAPS ARE DECLARED VALUES rather than whatever the line-height leaves over, which is
   the property the cell was missing. */
.cfdb-commentary { display:inline-flex; align-items:baseline; gap:.45rem; }
.cfdb-commentary-marks { white-space:nowrap; }
.cfdb-commentary-stacked { display:flex; flex-direction:column; align-items:flex-start;
                           gap:.15rem; }
/* A164 (cfdb-main-R-1141). THE RECORD WRAPPED BELOW THE TEAM NAME IN ALL SEVEN TABLES, AND THE
   CAUSE IS NOT THE ONE IT LOOKS LIKE. `_team_identity` emits {name-anchor}{record} as siblings,
   and `.cfdb-teamlink` above is `display:flex` — a BLOCK-LEVEL box — so the record could never
   share its line whatever the column width.

   🚨 THE OBVIOUS SUSPECT WAS TESTED AND EXONERATED. `.cfdb-table .cfdb-team`'s
   `display:inline-block; max-width:100%` reads like the culprit and is not: forced to
   `max-width:none` the record still wrapped 0/4, and removing that rule's whole ellipsis
   cluster still wrapped 0/4. Switching `.cfdb-teamlink` to inline-flex fixed 3 of 4 in the same
   frame. **The rule that looked wrong was innocent and the rule nobody suspected was the cause**
   — which is why this is a wrapper rather than an edit to either of them.

   ✅ A WRAPPER, NOT A CHANGE TO `.cfdb-teamlink`, BECAUSE THAT CLASS IS NOT ONLY TODAY'S.
   `table.record_span` is also composed by `schedule.py` in a different shape, and `.cfdb-team`
   is read by the game cards and the legend. A new class changes exactly the cells
   `_team_identity` draws and nothing else.

   ✅ AND IT IS `.cfdb-player`'s PATTERN (above), DELIBERATELY THE SAME IDEA AND NOT A SECOND
   ONE: a flex row on a baseline, `min-width:0` on the part that must give up pixels first, so
   the NAME ellipsises and the record — two characters and a hyphen — never does. The 4th of
   those four rows is why the min-width matters: at inline-flex alone it still wrapped, because
   a flex item defaults to `min-width:auto` and refuses to shrink below its content.
   ⚠️ R-129's BOUNDARY IS UNMOVED: the record stays OUTSIDE the anchor and the rank stays inside
   `team_cell`. This wraps both; it crosses neither. */
/* 🚨 A165 (cfdb-main-R-1300). `align-items:center`, NOT `baseline`, AND THE REASON IS THAT ONE
   OF THESE TWO CHILDREN HAS NO TEXT TO TAKE A BASELINE FROM.
   > **MARC, Today v05:** *"The teams (logo, name, record) are not aligned vertically. Review the
   > image. Record needs to move up."*

   📊 MEASURED IN CHROMIUM ON THE REAL PAGE, 160 identity cells across four panels: the record's
   alphabetic baseline sat **9.5–10px BELOW the team name's**, identically at 1300px and 1600px.
   ⚠️ A164 shipped this cell and reported `gapX 6.4px` — a HORIZONTAL fact, measured on the axis
   it was asked about. **Both readings were true at once**: the record was on the line and sitting
   a logo-height below it.

   THE CAUSE: `.cfdb-identity` baseline-aligns two children. The second is the record's text; the
   first is `.cfdb-teamlink`, itself a flex container whose first item is an EMPTY 28px logo box.
   A flex container with no in-flow text synthesises its baseline from its BOTTOM MARGIN EDGE, so
   the record was aligning to the bottom of the logo rather than to the name.

   📊 THE CANDIDATES, MEASURED — and the obvious one was rejected on evidence:

       control                                  record +9.5/+10   logo  0
       negative control (a no-op rule)          record +9.5/+10   logo  0   <- instrument reads zero
       A: teamlink align-items:baseline         record +0.2/+0.5  logo +5/+6.2   ❌ THE LOGO MOVES
       B: this rule                             record −1/−0.5    logo  0        ✅

   🚨 **A LOOKS BETTER ON THE NUMBER MARC COMPLAINED ABOUT AND IS THE WRONG FIX.** It trades the
   record's misalignment for the logo's: baseline-aligning the anchor grows the flex line, and a
   center-aligned 28px disc then sits 5-6px off the name it belongs to. **The logo is an identity
   affordance on Marc's page and it is optically center-aligned to the name today.**

   ✅ WHY CENTER IS RIGHT HERE RATHER THAN A COMPROMISE: both children are single-line text of
   almost the same size (12.48px and 12px), so their centers and their baselines coincide to
   within the font-size difference — which is the −0.5/−1px residual, and is the whole error.
   ⚠️ A redundant `.cfdb-teamlink{align-items:center}` was tested alongside and changed nothing,
   because that rule is already center; this is one property, not two. */
.cfdb-identity { display:flex; align-items:center; gap:.4rem; min-width:0; }

/* ── A175 (cfdb-main-R-1750). THE SPARK BARS ───────────────────────────────────────────────
   > MARC, Today v04: "Can we add horizontal spark bars in the Total, Rush, and Pass cells.
   > Make them all proportionate and relative to the max of the Total column. Bars from the
   > left. The number in the cell right aligned, not at the end of the bar."

   🚨 EVERY CLAUSE OF THAT SENTENCE IS A RULE HERE, and the last one is the easy one to lose:
   the NUMBER is right-aligned in the CELL, so it sits at the cell's right edge whatever the
   bar does. A number riding the bar's end would encode the value twice and align nothing.

   The bar is BEHIND the number rather than beside it — one cell, no second column, and no
   width taken from a table that A165 spent a round tightening. `position:absolute` inside a
   `position:relative` cell keeps it out of the text flow entirely.

   ⚠️ `currentColor` AT LOW ALPHA, NOT A PALETTE COLOR. These bars carry no category — they
   are the same measure at three scales — so a hue would imply a distinction that is not
   there, and `currentColor` inherits the theme both ways with no light-dark() to maintain. */
.cfdb-spark { position:relative; display:block; text-align:right; }
/* A178 (cfdb-main-R-1852). THE BORDER MARC ASKED FOR, AND THE TWO THINGS THAT MADE IT MORE
   THAN ONE DECLARATION.
   > MARC, v10: "Can you add a 50% dark gray border to the bars to make them pop."

   🚨 1. `opacity` WOULD HAVE EATEN IT. The fill used to be `background:currentColor` plus
   `opacity:.15` on the ELEMENT, and element opacity multiplies everything the element paints
   — border included. A 50% border under a 0.15 element is a 7.5% border, which is not a
   border. So the fill's transparency moves into the background COLOR via color-mix (used
   sixteen times elsewhere in this file), and opacity comes off entirely. The fill is
   unchanged at 15%; only where the 15% is applied moved.

   🚨 2. "DARK GRAY" IS INVISIBLE ON THE DARK PAGE. This site renders on #ffffff and on
   #0e1117, and a literal dark gray disappears into the second — B109's finding, and the same
   class that cost cfdb-wta-R-1291 a wrong team color on 10.89% of games. `light-dark()` is
   the site's existing mechanism for exactly this and follows the same `color-scheme` property
   Streamlit sets, so the browser resolves it with no Python in the loop.

   ⚠️ `box-sizing:border-box` IS LOAD-BEARING. The width is an inline percentage of the cell
   (`today.py`'s `_spark_cell`); without it a 1px border on each side makes every bar 2px
   wider than the share it encodes, which is a quantity being misdrawn rather than a style. */
.cfdb-spark-bar { position:absolute; left:0; top:50%; transform:translateY(-50%);
                  height:1.05em; box-sizing:border-box;
                  background:color-mix(in srgb, currentColor 15%, transparent);
                  border:1px solid light-dark(rgba(0,0,0,.5), rgba(255,255,255,.5));
                  border-radius:2px; pointer-events:none; }
.cfdb-spark-value { position:relative; }
.cfdb-identity > .cfdb-teamlink { min-width:0; }
.cfdb-identity > .cfdb-team-record { flex:0 0 auto; margin-left:0; }
.cfdb-identity .cfdb-team { min-width:0; }
.cfdb-ind { display:inline-block; width:.72em; height:.72em; box-sizing:border-box;
            border:1.5px solid transparent; }
/* A SHAPE PER POSITION, so a single indicator can be matched to its legend entry without
   counting its neighbors. All three were circles, which meant position was the only thing
   telling them apart — and position is unreadable the moment one of them is invisible. */
.cfdb-sh-upset { border-radius:50%; }
.cfdb-sh-cover { border-radius:2px; }
.cfdb-sh-over  { border-radius:1px; transform:rotate(45deg); width:.62em; height:.62em; }
/* `none` is a RESERVED BLANK, not an omission: a strip that appears only on completed games
   shifts the columns beside it the moment a week is half played. It means NOT PLAYED YET. */
.cfdb-ind-none { background:transparent; border-color:transparent; }
/* `quiet` means ANSWERED AND UNREMARKABLE — a game that was played and was not an upset.
   That used to render as `none`, i.e. as nothing, which made it indistinguishable from a game
   nobody has played and left the first slot blank on every completed game of a normal week.
   Two visible indicators then sat in slots two and three and read as slots one and two. */
/* R-160. THE QUIET STATE TAKES THE ACCENT, as Marc asked. The caution stands and is worth
   leaving here: it means "played, nothing remarkable", and an accent border can read as
   active. It is distinguishable from the covered/over indicators by SHAPE — circle against
   square and diamond — so the color is not carrying the distinction on its own. */
.cfdb-ind-quiet { background:transparent; border-color:#1f6feb; opacity:.45; }
/* R-164, Marc's choice of the three offered. `nodata` means WE HOLD NO CLOSING LINE, which
   is a third thing again: not "not played" (nothing drawn) and not "played, unremarkable"
   (the quiet accent). Closing lines exist for roughly 3,200 games in the whole warehouse, so
   on a historical week this is the common case and it deserves to say so rather than leave
   the reader counting empty slots. Dotted and gray: present, and explicitly not an answer. */
/* R-171. A DASH, NOT AN OUTLINE. The dotted version still read as a value being shown —
   with Division on All Divisions, lower-division games carry no spread or total at all and
   the strip came out as three faint outlines with nothing saying why.

   It keeps `.cfdb-ind`'s box so R-166's alignment survives, and cancels the diamond's
   rotation, which would otherwise tip the dash onto its side in the third slot. */
/* WIDTH AND HEIGHT ARE RESTATED, AND font-size IS NOT TOUCHED. `.cfdb-ind` sizes its box in
   `em` of its OWN font-size, so setting a font-size here silently grew the box — measured:
   four distinct indicator widths across a page instead of two, which is R-166's alignment
   coming apart one slot at a time. The dash inherits its size and the box is pinned. */
.cfdb-ind-nodata { background:transparent; border-color:transparent;
                   color:rgba(127,127,127,.85); transform:none;
                   width:.72em; height:.72em; line-height:.66em;
                   text-align:center; font-weight:700; }
.cfdb-ind-open { background:transparent; border-color:currentColor; }
.cfdb-ind-fill { background:currentColor; border-color:currentColor; }
/* A push is neither: half-filled reads as "landed on the number" without a fourth color. */
.cfdb-ind-push { background:linear-gradient(90deg, currentColor 50%, transparent 50%);
                 border-color:currentColor; }
.cfdb-acc { color:var(--cfdb-link); }
.cfdb-u1  { color:var(--cfdb-u1); }
.cfdb-u2  { color:var(--cfdb-u2); }
.cfdb-u3  { color:var(--cfdb-u3); }

/* R-149. THE LINE BLOCK — one cell of the card grid, three columns of its own, on BOTH card
   variants. The result card fills them label / line / actual; the preview card fills them
   label / line / move.

   THE RULES ARE WHAT MAKE IT READ AS A BLOCK. A border-left here draws the divider between
   the team column and the line block; the box score's own left border (`cfdb-gc-bl`) draws
   the one on the other side. Both run the full three rows because every row of the grid has
   a cell in this track — including the header row, which is why `_line_block_header` exists
   rather than an empty div.

   The padding is deliberately symmetrical and generous: it is the gap between the rules and
   the numbers, and it is what Marc meant by tightening the block up. The inner columns got
   NARROWER as the outer padding got wider, which is why MIDDLE_TRACK grew by only 1rem. */
.cfdb-gc-mid { display:grid; grid-template-columns:3.3rem 2.9rem 3.2rem; align-items:center;
               font-size:.9rem; font-variant-numeric:tabular-nums; padding:.1rem .9rem;
               border-left:1px solid rgba(127,127,127,.30); }
/* ONE WEIGHT, ONE OPACITY, ACROSS THE WHOLE BLOCK. The actual was 600 on the result card and
   the line was 600 on the preview card, so the emphasis landed on a different column
   depending on whether the game had been played. The headers say which column is which now,
   which is what makes the weight unnecessary rather than merely inconsistent. */
.cfdb-gc-mid-label  { opacity:.55; font-size:.8rem; }
.cfdb-gc-mid-line   { text-align:right; }
.cfdb-gc-mid-actual { text-align:right; }
.cfdb-gc-mid-head span { opacity:.55; font-size:.72rem; font-weight:600;
                         letter-spacing:.02em; }
/* R-552. THE `@media (prefers-color-scheme: dark)` BLOCK THAT USED TO BE HERE IS GONE, and
   its rules now live as tokens in the `:root` above — see the comment there for why each one
   needed a different tool. Deleted rather than corrected, which is R-547's reasoning applied a
   second time: the question the media query asks is the wrong question, so correcting its
   values would only have banked the same bug again.

   ⚠️ THE ONE RULE THAT LEFT NO TOKEN BEHIND is the pair this block set on `.cfdb-table th`
   and `.cfdb-table td` — those two ARE the light declarations now, because a derived tint is
   correct in both themes and there is nothing left to override. If a future round adds a
   dark-only rule here, it is almost certainly a mistake: there is no supported way to ask
   "is the APP dark" in CSS other than the `color-scheme` property, and `light-dark()` is how
   you consume it. */
</style>
"""


def inject_tables() -> None:
    st.markdown(TABLE_CSS, unsafe_allow_html=True)


def hide_nav_entries(keys) -> None:
    """Hide specific sidebar links while leaving their routes intact.

    The Team page has its own index — Teams is searchable, conference-filtered and already
    the way people reach it — so a nav slot landing on an arbitrary team is worse than no
    slot. But st.navigation does routing as well as the sidebar, so the page has to stay
    registered or every team link on the site becomes a dead one.

    Scoped to the sidebar nav so it cannot hit an in-page link to the same destination.
    """
    if not keys:
        return
    selectors = ", ".join(
        f'[data-testid="stSidebarNav"] a[href$="/{key}"]' for key in keys)
    st.markdown(f"<style>{selectors} {{ display:none !important; }}</style>",
                unsafe_allow_html=True)
