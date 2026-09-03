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
   meaning; colour is the second signal, so it survives greyscale (AC-G.21/22). */
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
.cfdb-footer { margin-top:2.5rem; padding-top:.8rem; border-top:1px solid #e3e6ea;
  font-size:.82rem; opacity:.75; }
.cfdb-readiness { font-size:.8rem; opacity:.7; font-family:ui-monospace,Menlo,monospace; }

@media (prefers-color-scheme: dark) {
  .cfdb-state { --cfdb-border:#333a45; --cfdb-bg:#1b1f27; }
  .cfdb-skel-row { background:linear-gradient(90deg,#242933 25%,#2b313c 37%,#242933 63%);
    background-size:400% 100%; }
  .cfdb-footer { border-top-color:#333a45; }
}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(TABLE_CSS, unsafe_allow_html=True)


TABLE_CSS = """
<style>
.cfdb-table { width:100%; border-collapse:collapse; font-size:.9rem;
    table-layout:fixed; }
.cfdb-table td, .cfdb-table th { overflow:hidden; text-overflow:ellipsis; }
.cfdb-table caption { caption-side:top; text-align:left; font-size:.8rem; opacity:.6;
  padding-bottom:.4rem; }
.cfdb-table th { text-align:left; font-weight:600; font-size:.78rem; letter-spacing:.02em;
  text-transform:uppercase; opacity:.65; border-bottom:1px solid #d7dae0;
  padding:.45rem .55rem; }
.cfdb-table td { padding:.42rem .55rem; border-bottom:1px solid #eef0f3; }
.cfdb-table tbody tr:hover { background:rgba(31,111,235,.05); }
/* Linked rows. The anchor fills the cell so the whole row is a target, while staying a
   real <a href> — which is what makes middle-click and copy-link work (AC-G.13). The row
   link inherits colour so a table does not turn into a wall of blue; the column-specific
   link (a team name) is visually distinct, per AC-2.5. */
.cfdb-table td a.cfdb-cell-link { display:block; color:inherit; text-decoration:none;
    margin:-.42rem -.55rem; padding:.42rem .55rem; }
.cfdb-table td a.cfdb-cell-link-alt { color:#1f6feb; font-weight:600; }
.cfdb-table td a.cfdb-cell-link-alt:hover { text-decoration:underline; }
.cfdb-table tr.cfdb-linked { cursor:pointer; }
.cfdb-dataset { font-size:.78rem; opacity:.72; margin:-.25rem 0 .6rem; }
.cfdb-dataset a { color:#1f6feb; text-decoration:none; }
.cfdb-dataset a:hover { text-decoration:underline; }
.cfdb-footer a { color:#1f6feb; text-decoration:none; }
.cfdb-footer a:hover { text-decoration:underline; }
.cfdb-footer-links { opacity:.85; }
.cfdb-footer-links a[aria-label] { display:inline-block; min-width:1.4em;
    text-align:center; font-weight:700; }
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
.cfdb-winner { color:#1f6feb; font-weight:700; margin-right:.15rem; }
.cfdb-winner-spacer { display:inline-block; width:.75em; }
.cfdb-details { opacity:.55; font-size:1rem; }
/* R-101: the neutral-site glyph now shares a column with the matchup glyph, so it
   needs its own separation from it rather than a column border. */
.cfdb-neutral { opacity:.55; margin-left:.35rem; }
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
.cfdb-team { margin-left:.4rem; }
.cfdb-rank { font-size:.72rem; font-weight:700; opacity:.7; margin-left:.3rem; }
.cfdb-daygroup { font-weight:600; margin:1.1rem 0 .3rem; font-size:.95rem; }
/* R-088: the record sits beside the team name, smaller and regular weight — not its own
   column, which would cost a column's width for two characters. */
.cfdb-team-record { font-size:.75rem; font-weight:400; opacity:.65; margin-left:.4rem; }
/* R-027: weather is a glyph plus a temperature, or a dome glyph alone. */
.cfdb-wx { white-space:nowrap; font-size:.85rem; }
/* R-110: THE BROWSER DECIDES HOW MANY CARDS FIT, NOT THE SERVER.
   Streamlit renders server-side and cannot measure a viewport, so `st.columns(2)` would be a
   FIXED two-up that keeps two cards side by side on a phone. `auto-fit` + `minmax` costs no
   JavaScript and no custom component, and reflows to one column on its own.

   560px, down from 620px: R-114 deleted the box score's row-label column (the team row IS the
   label now) and moved the kickoff out of a left gutter into row 1, so the card genuinely
   needs less. Measured content: teams 235 + numerics 13.7rem/219 + padding 48 + gap 14.

   auto-FILL, NOT auto-FIT, AND THE DIFFERENCE IS VISIBLE ON EVERY MIDWEEK DAY. `auto-fit`
   COLLAPSES tracks it cannot fill, so a Sunday with one game rendered that card at 1460px
   while every other day rendered 723px — measured, not guessed. `auto-fill` keeps the empty
   track, so a lone card is the same size as a card with a neighbour and the page stops
   changing shape according to how many games were played. */
.cfdb-cardgrid { display:grid; gap:.7rem .9rem; align-items:stretch;
                 grid-template-columns:repeat(auto-fill, minmax(560px, 1fr)); }
.cfdb-gamecard { display:flex; flex-direction:column; height:100%;
                 padding:.55rem .7rem; border:1px solid rgba(0,0,0,.10);
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
.cfdb-gc-market { display:grid; grid-template-columns:4.4rem 1fr 3.6rem; font-size:.85rem;
                  align-items:center; font-variant-numeric:tabular-nums; }
.cfdb-gc-market-label { opacity:.6; font-size:.78rem; }
.cfdb-gc-market-value { text-align:right; font-weight:600; }
.cfdb-gc-market-move { text-align:right; opacity:.6; font-size:.76rem; }
/* R-092: why the quarters are missing, not merely that they are. */
.cfdb-ls-why { font-size:.72rem; opacity:.6; margin-top:.15rem; text-align:right; }
/* R-015: anchored to the bottom so two cards in one grid row end level. */
.cfdb-gamecard-meta { font-size:.78rem; opacity:.7; margin-top:auto; padding-top:.35rem; }
.cfdb-gamecard-meta a { color:inherit; text-decoration:none; }
/* R-119: the card's only route to Matchup, and it was too small to read as an affordance. */
.cfdb-gamecard-meta .cfdb-details { font-size:1.15rem; opacity:.7; vertical-align:-.1em; }
.cfdb-gamecard-meta a:hover .cfdb-details { opacity:1; }
/* R-107: a card is not a table cell, so it cannot borrow .cfdb-cell-link — that one is
   display:block, which inside a flex row would make the anchor a full-width item. */
/* R-117: THE COLOUR HAS TO MOVE OFF THE ANCHOR AND ONTO THE NAME.
   `color:inherit` on the record was not enough and the measurement said so: it inherits from
   its parent, the parent is the anchor, and Streamlit's own `a` rule paints that rgb(0,84,163)
   — so the record rendered in link blue and read as a second link, which is the exact failure
   R-117 warned about. Both rules below are needed: the anchor gives up the colour, and the
   NAME takes the accent explicitly. The record then inherits body text and stays dimmed by
   its own opacity, in either theme, with no hardcoded palette. */
.cfdb-teamlink { color:inherit !important; text-decoration:none; display:flex;
                 align-items:center; min-width:0; }
.cfdb-teamlink .cfdb-team { color:#1f6feb; }
.cfdb-teamlink:hover .cfdb-team { text-decoration:underline; }
.cfdb-teamlink .cfdb-team-record { color:inherit; text-decoration:none; }
.cfdb-teamlink:hover .cfdb-team-record { text-decoration:none; }
/* R-121: the monogram sits BEHIND the image, so a file that goes missing later paints the
   same grey disc a null gives instead of the browser's broken-image box. Streamlit strips
   event handlers, so `onerror` is not available here. */
.cfdb-logo-box { display:inline-block; flex:0 0 auto; vertical-align:middle;
                 border-radius:50%; background:rgba(127,127,127,.14); margin-right:.4rem; }
.cfdb-logo-box .cfdb-logo { display:block; margin-right:0; }
/* R-102: the legend the R-026 icon-only exception leans on. */
.cfdb-legend { font-size:.78rem; opacity:.65; margin:.2rem 0 .5rem; }
.cfdb-legend span { margin-right:.9rem; white-space:nowrap; }
@media (prefers-color-scheme: dark) {
  .cfdb-table th { border-bottom-color:#333a45; }
  .cfdb-table td { border-bottom-color:#242933; }
  /* A 10%-black border on a #0e1117 background is invisible, so every card edge
     disappeared in dark mode and the grid read as one undivided block. */
  .cfdb-gamecard { border-color:#333a45; }
}
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
