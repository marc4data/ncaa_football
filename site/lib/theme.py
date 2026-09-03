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
/* R-133. THE SPACER'S WIDTH IS IN `em`, SO IT ONLY MATCHES WHILE THE FONT SIZES MATCH.
   Both carry the same font-size deliberately: if the spacer stops resolving to the glyph's
   width the two scores stop aligning vertically, which is the whole thing R-120 was built to
   prevent and the reason the size is stated twice rather than inherited. */
.cfdb-winner { color:#1f6feb; font-weight:700; margin-right:.15rem;
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
.cfdb-details { opacity:.85; font-size:1.3rem; color:#1f6feb; vertical-align:-.12em; }
/* R-101: the neutral-site glyph now shares a column with the matchup glyph, so it
   needs its own separation from it rather than a column border. */
.cfdb-neutral { opacity:.85; margin-left:.4rem; font-size:1.15rem; color:#1f6feb;
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
   track, so a lone card is the same size as a card with a neighbour and the page stops
   changing shape according to how many games were played. */
.cfdb-cardgrid { display:grid; gap:.7rem .9rem; align-items:stretch;
                 grid-template-columns:repeat(auto-fill, minmax(580px, 1fr)); }
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
   the cursor. The colour rules stay because the dense table wraps whole CELLS in an anchor,
   which it did before R-117 too, so the record still needs telling not to look like a link
   there. R-136: the underline takes the LINK colour instead of the anchor's inherited one. */
.cfdb-teamlink { color:inherit !important; text-decoration:none; display:flex;
                 align-items:center; min-width:0; }
.cfdb-teamlink .cfdb-team { color:#1f6feb; text-decoration-color:#1f6feb; }
.cfdb-teamlink:hover .cfdb-team { text-decoration:underline; }
.cfdb-team-record { text-decoration:none !important; }
a .cfdb-team-record, .cfdb-cell-link .cfdb-team-record { color:inherit; }
/* R-136: Streamlit underlines anchors and draws the line in the ANCHOR's colour, which is the
   body text here — a light rule under blue text, which fights on dark.
   `!important` because Streamlit's own `.stMarkdown a` outranks a two-class selector; measured
   without it the decoration stayed rgb(49,51,63) in light and rgb(250,250,250) in dark. */
.cfdb-table a, .cfdb-cell-link, .cfdb-teamlink .cfdb-team {
    text-decoration-color:#1f6feb !important; }
/* R-121: the monogram sits BEHIND the image, so a file that goes missing later paints the
   same grey disc a null gives instead of the browser's broken-image box. Streamlit strips
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
/* R-174. THE KEY BOX CENTRES ITS CONTENTS, AND A POSITIONAL MARGIN DEFEATS THAT.
   `.cfdb-neutral` carries `margin-left:.4rem` for the ROW, where the diamond trails the
   kickoff time and needs a gap (R-146). Inside a 1.6rem centred box that same margin is .4rem
   of left padding with nothing to balance it, so the glyph sat right of centre — exactly what
   Marc saw. Cancelled in the legend only; it is still doing its job elsewhere. The other four
   classes are listed pre-emptively because they carry the same shape of margin and the next
   mark added to the legend would otherwise repeat this. */
.cfdb-legend-key .cfdb-neutral,
.cfdb-legend-key .cfdb-team,
.cfdb-legend-key .cfdb-rank,
.cfdb-legend-key .cfdb-winner,
.cfdb-legend-key .cfdb-ind { margin-left:0; margin-right:0; }
/* R-175: the dome inherits colour and sizes with its row, like every other mark. */
.cfdb-dome { width:1.15em; height:1.15em; vertical-align:-.22em; }
.cfdb-legend-key .cfdb-dome { vertical-align:-.28em; }
/* R-177: the worked examples ride the long column's heading line. */
.cfdb-legend-head { display:flex; align-items:baseline; justify-content:space-between;
                    gap:.8rem; }
.cfdb-legend-egs { display:inline-flex; gap:.9rem; }
.cfdb-legend-eg { display:inline-flex; }
.cfdb-legend-egcap { margin-top:.7rem; font-size:.76rem; opacity:.6; }
/* The groups stack in the left column, so a second heading needs air above it. */
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
   controls size, baseline and colour for all six states; the semantics are unchanged. */
.cfdb-strip { display:inline-flex; gap:.2rem; align-items:center; vertical-align:-.08em; }
.cfdb-strip-gap { display:inline-block; width:.45rem; }
.cfdb-ind { display:inline-block; width:.72em; height:.72em; box-sizing:border-box;
            border:1.5px solid transparent; }
/* A SHAPE PER POSITION, so a single indicator can be matched to its legend entry without
   counting its neighbours. All three were circles, which meant position was the only thing
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
   square and diamond — so the colour is not carrying the distinction on its own. */
.cfdb-ind-quiet { background:transparent; border-color:#1f6feb; opacity:.45; }
/* R-164, Marc's choice of the three offered. `nodata` means WE HOLD NO CLOSING LINE, which
   is a third thing again: not "not played" (nothing drawn) and not "played, unremarkable"
   (the quiet accent). Closing lines exist for roughly 3,200 games in the whole warehouse, so
   on a historical week this is the common case and it deserves to say so rather than leave
   the reader counting empty slots. Dotted and grey: present, and explicitly not an answer. */
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
/* A push is neither: half-filled reads as "landed on the number" without a fourth colour. */
.cfdb-ind-push { background:linear-gradient(90deg, currentColor 50%, transparent 50%);
                 border-color:currentColor; }
.cfdb-acc { color:#1f6feb; }
.cfdb-u1  { color:#d9a406; }
.cfdb-u2  { color:#e06c1f; }
.cfdb-u3  { color:#d2333a; }

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
@media (prefers-color-scheme: dark) {
  .cfdb-table th { border-bottom-color:#333a45; }
  .cfdb-table td { border-bottom-color:#242933; }
  /* A 10%-black border on a #0e1117 background is invisible, so every card edge
     disappeared in dark mode and the grid read as one undivided block. */
  .cfdb-gamecard { border-color:#333a45; }
  /* R-131. #1f6feb on #0e1117 measures about 3.6:1 — below the 4.5:1 a small glyph needs, and
     no amount of font-weight changes a luminance. #58a6ff is the standard lift and clears it. */
  .cfdb-details, .cfdb-neutral, .cfdb-winner { color:#58a6ff; }
  /* R-141: the accent indicators need the same lift as every other glyph on dark. */
  .cfdb-acc { color:#58a6ff; }
  .cfdb-u1 { color:#e8b931; } .cfdb-u2 { color:#f0803c; } .cfdb-u3 { color:#f0555c; }
  .cfdb-teamlink .cfdb-team { color:#58a6ff; text-decoration-color:#58a6ff; }
  .cfdb-table a, .cfdb-cell-link, .cfdb-teamlink .cfdb-team {
      text-decoration-color:#58a6ff !important; }
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
