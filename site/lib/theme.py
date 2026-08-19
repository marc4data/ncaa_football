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
