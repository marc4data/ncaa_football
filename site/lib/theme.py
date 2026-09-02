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

   THE MINIMUM IS MEASURED FROM THE CONTENT, NOT FROM THE CURRENT RENDER. The card Marc
   screenshotted occupied ~1,400px, almost all of it the empty space R-105 removes. Widest
   thing a card must hold on one line, at the sizes declared below:

     time      "12:00 PM PDT"                                     ~ 92px
     teams     marker 14 + logo 20 + rank 22 + 18ch name 135 + record 40 + gaps  ~ 235px
     detail    label 5ch 42 + four quarters + OT + T at 2.6em 190 + marker 14    ~ 246px
     padding   card 22 + two 0.8rem gaps 26                                      ~  48px

   621px rounds to 620. At a 1,400px content column that is two-up with room; below ~1,260px
   the browser drops to one. `align-items:stretch` keeps two cards in a row the same height —
   R-015 horizontally is undone by ragged heights vertically. */
.cfdb-cardgrid { display:grid; gap:.7rem .9rem; align-items:stretch;
                 grid-template-columns:repeat(auto-fit, minmax(620px, 1fr)); }
.cfdb-gamecard { display:flex; flex-direction:column; height:100%;
                 padding:.55rem .7rem; border:1px solid rgba(0,0,0,.10);
                 border-radius:6px; }
.cfdb-gamecard-top { display:flex; gap:.8rem; align-items:flex-start; }
/* R-108: kickoff on the left, where a schedule is read from. */
.cfdb-gamecard-time { flex:0 0 auto; font-size:.8rem; opacity:.7; padding-top:.15rem;
                      white-space:nowrap; font-variant-numeric:tabular-nums; }
.cfdb-gamecard-teams { flex:1 1 auto; min-width:0; }
/* R-105: THE ROW HAS ONE CHILD, AND THAT IS THE WHOLE FIX.
   It used to have four or five — logo, rank badge, name, record, points — all interpolated
   straight into a `justify-content:space-between` flex row, which distributed every one of
   them across the full width. The .4rem margins were applied and then overwhelmed. */
.cfdb-gamecard-row { display:flex; align-items:center; padding:.12rem 0; min-width:0; }
/* THE BOUNDARY: table.team_cell() is built for a TABLE cell, where the column supplies the
   box. Its output is several sibling spans, so dropping it into a flex container makes each
   span a flex item. Anything putting team_cell() in a flex context must wrap it. */
.cfdb-teamcluster { display:flex; align-items:center; min-width:0; }
.cfdb-teamcluster .cfdb-team { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* R-112: which side is home, in one character. "@ TCU" reads as "at TCU" under the
   away-over-home convention; "vs TCU" says there is no home side to read into it. */
.cfdb-athome { display:inline-block; width:1.5em; flex:0 0 auto; font-size:.8rem;
               opacity:.6; }
.cfdb-gamecard-detail { flex:0 0 auto; text-align:right; }
/* R-015: anchored to the bottom so two cards in one grid row end level. */
.cfdb-gamecard-meta { font-size:.78rem; opacity:.7; margin-top:auto; padding-top:.3rem; }
.cfdb-gamecard-meta a { color:inherit; text-decoration:none; }
.cfdb-linescore { border-collapse:collapse; font-size:.78rem; table-layout:fixed; }
.cfdb-linescore th, .cfdb-linescore td { padding:.05rem .35rem; text-align:right;
                                         font-variant-numeric:tabular-nums; }
.cfdb-linescore th { opacity:.6; font-weight:600; }
.cfdb-ls-team { text-align:left; opacity:.75; padding-right:.5rem !important;
                overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cfdb-ls-ot { font-weight:700; }
/* R-109: the score is the last column of the box score, not a separate block. */
.cfdb-ls-total { font-weight:700; }
/* R-113: the marker's own column, so it is reserved on the losing row too. */
.cfdb-ls-mark { width:1.2em; padding:0 !important; text-align:right !important; }
/* R-092: why the quarters are missing, not merely that they are. */
.cfdb-ls-why { font-size:.72rem; opacity:.6; margin-top:.15rem; text-align:right; }
/* R-106: the pre-kick occupant of the same box. */
/* R-015 APPLIES HERE TOO. Without a fixed layout the market block sizes itself to its own
   contents, so a card whose line has not moved renders a narrower box than the one beside it
   and the two O/U numbers sit at different x. Constant widths rather than a computed geometry
   because, unlike the box score, nothing about this block varies with the page. */
.cfdb-market { border-collapse:collapse; font-size:.78rem; margin-left:auto;
               table-layout:fixed; }
.cfdb-market td { padding:.05rem .35rem; text-align:right;
                  font-variant-numeric:tabular-nums; }
.cfdb-market-label { text-align:left !important; opacity:.6; white-space:nowrap; }
.cfdb-market-move { opacity:.6; font-size:.72rem; }
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
