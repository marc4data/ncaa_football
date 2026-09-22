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
.cfdb-sc-ring { stroke-opacity:.35; }

/* ── A190: the distance table beside the chart ────────────────────────────────────────────
   Six columns in ~18% of the row, so the team name is the only flexible one and everything
   else is sized to its content. */
/* ⚠️ THE `min-width` IS THE STACKING MECHANISM, NOT A COSMETIC FLOOR. It equals what the
   row's first line needs (rank 17.6 + logo 17.6 + widest name 116.9 + gaps 8 = 160.1), and
   Streamlit's `stHorizontalBlock` is `flex-wrap:wrap` with `min-width:auto` columns — so
   below roughly 1400px the column cannot shrink past this and drops to its own full-width
   line beneath the chart. Container-driven, so it is right with the sidebar open or closed. */
.cfdb-far { font-size:.72rem; min-width:10rem; }
.cfdb-far-head { font-weight:700; font-size:.7rem; letter-spacing:.04em;
                  text-transform:uppercase; opacity:.65; padding-bottom:.2rem;
                  border-bottom:1px solid var(--cfdb-edge); margin-bottom:.15rem; }
/* Two lines: rank + logo + NAME across the top, the three small facts under it. See
   `today._distance_table` for the measurement that forced it — six columns on one line need
   245.9px and Marc's 15-20% band gives 168.4px at 1440. */
.cfdb-far-row { display:grid; grid-template-columns:1.1rem 1.1rem minmax(0,1fr);
                align-items:center; gap:.1rem .25rem; padding:.2rem 0;
                border-bottom:1px solid var(--cfdb-rule-soft); }
.cfdb-far-meta { grid-column:3 / -1; display:flex; gap:.25rem; align-items:baseline;
                 font-size:.64rem; opacity:.7; white-space:nowrap; }
.cfdb-far-slash { opacity:.4; }
.cfdb-far-rank { font-weight:700; opacity:.45; font-variant-numeric:tabular-nums;
                  text-align:right; font-size:.68rem; }
.cfdb-far-logo { width:16px; height:16px; object-fit:contain; }
.cfdb-far-team { min-width:0; overflow:hidden; white-space:nowrap;
                  text-overflow:ellipsis; font-weight:600; }
.cfdb-far-rec { opacity:.5; font-weight:400; margin-left:.25rem; font-size:.66rem; }
.cfdb-far-num { font-variant-numeric:tabular-nums; text-align:right; opacity:.8; }
.cfdb-far-foot { opacity:.55; font-size:.62rem; margin-top:.3rem; line-height:1.25; }
.cfdb-far-none { opacity:.6; font-size:.7rem; padding:.4rem 0; }
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
.cfdb-sc-axis { fill:currentColor; fill-opacity:.7; font-size:11px; }
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
  --cfdb-card-team-w:    2.75rem;  /* 44px; widest abbreviation "MRMK" draws 41.6px */
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
  --cfdb-u1:   light-dark(#d9a406, #e8b931);
  --cfdb-u2:   light-dark(#e06c1f, #f0803c);
  --cfdb-u3:   light-dark(#d2333a, #f0555c);
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
.cfdb-scroll { overflow-x:auto; overflow-y:auto; max-height:70vh; }
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
.cfdb-table td, .cfdb-table th { overflow:hidden; text-overflow:ellipsis; }
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
.cfdb-table th.cfdb-num, .cfdb-table td.cfdb-num { text-align:right; }
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
.cfdb-table .cfdb-team { display:inline-block; max-width:100%; vertical-align:bottom;
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
   bought was two-thirds of a blank screen at the foot of every page on the site. Measuring
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
.cfdb-cardcol-head { font-size:.72rem; font-weight:700; letter-spacing:.06em;
                     text-transform:uppercase; opacity:.6; padding-bottom:.15rem;
                     border-bottom:1px solid var(--cfdb-edge); }
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
.cfdb-card-team .cfdb-team { flex:0 0 100%; font-size:.68rem; }

.cfdb-card { min-width:0; padding:.4rem .45rem; border:1px solid var(--cfdb-edge);
             border-left:2px solid var(--cfdb-edge);
             background:var(--cfdb-row-alt, transparent); border-radius:3px;
             margin-bottom:.4rem;
             align-items:center; gap:.4rem;
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
/* ⚠️ AND EACH METRIC HOLDS ITS OWN CONTENT. `flex:1 1 0` split the block into equal thirds
   regardless of what was in them, which is what wrapped `483` under its own `YDS`. */
.cfdb-card .cfdb-card-metric { flex:0 0 auto; min-width:max-content; }
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
/* 1.7rem was 27.2px against a widest drawn jersey of 25.5px; 1.6rem still clears it. */
.cfdb-card .cfdb-player-jersey { min-width:1.6rem; }
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
.cfdb-card-metrics { display:flex; gap:.25rem; align-items:baseline; margin:0;
                     justify-content:flex-end; }
.cfdb-card-metric { display:flex; flex-direction:column; min-width:0; flex:1 1 0;
                    text-align:right; }
.cfdb-card-metric .cfdb-card-value { font-size:1.05rem; font-weight:700; line-height:1.15; }
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
   Only the logo is resized, because a 28px disc is a table-row affordance and this is a card. */
.cfdb-card-team .cfdb-logo-box, .cfdb-card-team .cfdb-logo { width:18px; height:18px; }
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
