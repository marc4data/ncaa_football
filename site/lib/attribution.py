"""Attribution, carried as data (§0.9, AC-G.41 to AC-G.44).

Sourced from the `attribution` COLUMN on the serving view, never from page config. That is
the whole design: a page physically cannot render the model's numbers without also having
fetched the string that says whose model it is.
"""
from typing import Optional

import pandas as pd
import streamlit as st

# Rendered as HTML, not markdown. The footer goes through st.markdown with
# unsafe_allow_html, which does NOT also parse markdown link syntax — so the previous
# `[text](url)` rendered as literal brackets and the attribution was not a link at all.
# F2-09 replaces the SENTENCE ABOUT attribution, not the attribution. The link stays —
# AC-G.43 requires it on every page — and the meta-commentary becomes a plug, which is
# better copy anyway.
CFBD_CREDIT = (
    'Data sourced from the '
    '<a href="https://collegefootballdata.com" target="_blank" rel="noopener">'
    'CollegeFootballData API</a>. Really cool site, check it out!')

# THE TWO ICONS ARE INLINE SVG FOR THE SAME REASON THE DOME IS (R-141, R-175).
#
# ✉ is U+2709, which has no fixed presentation: some platforms draw a hairline dingbat and
# others substitute a full-colour emoji, and nothing in CSS decides which. At the old size
# that was merely inconsistent. Making it bigger — which is the whole point of this change —
# makes the split conspicuous, so the glyph goes and a drawing takes its place. `in` as bold
# text had the matching problem: it was a monogram standing in for a logo, and it scaled up
# into looking like a typo rather than a mark.
#
# Both are sized in `em` against the footer's own font-size, so they track it (.cfdb-icon).
MAIL_MARK = (
    "<svg class='cfdb-icon' viewBox='0 0 20 20' fill='none' stroke='currentColor' "
    "stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<rect x='2' y='4.5' width='16' height='11' rx='1.5'/>"   # the envelope
    "<path d='M2.7 5.4 10 10.9l7.3-5.5'/>"                    # the flap
    "</svg>")

# LinkedIn's own mark. Used solely to link to Marc's own profile, which is what it is for.
LINKEDIN_MARK = (
    "<svg class='cfdb-icon' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>"
    "<path d='M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 "
    "2.94v5.67H9.35V9h3.42v1.56h.04c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 "
    "5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zm1.78 "
    "13.02H3.55V9h3.57v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 "
    "24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z'/>"
    "</svg>")

# This site is a portfolio piece, so the links are part of the point rather than an
# afterthought bolted to the bottom. The website link reads as a destination rather than as
# a bare hostname: a URL printed as its own label makes the reader parse a string to learn
# it is a personal site.
AUTHOR_LINKS = (
    '<a href="https://marc4data.netlify.app/" target="_blank" rel="noopener">'
    "Marc's Website</a>"
    ' · <a class="cfdb-icon-link" href="mailto:marc4data@gmail.com" title="Email Marc" '
    f'aria-label="Email Marc">{MAIL_MARK}</a>'
    ' · <a class="cfdb-icon-link" href="https://www.linkedin.com/in/marc4data/" '
    'target="_blank" rel="noopener" title="Marc on LinkedIn" '
    f'aria-label="Marc on LinkedIn">{LINKEDIN_MARK}</a>')


def model_attribution(df: Optional[pd.DataFrame]) -> None:
    """Render the attribution carried by this frame.

    If the column is absent or null, that is a DEFECT and the page says so rather than
    quietly omitting it — an unattributed prediction is the one thing the licence forbids.
    """
    if df is None or df.empty or "attribution" not in df.columns:
        st.caption("⚠ Attribution column missing from this view — this is a defect "
                   "(AC-G.41), not an absence of obligation.")
        return
    values = df["attribution"].dropna().unique()
    if len(values) == 0:
        st.caption("⚠ Attribution is null on every row — see AC-G.44.")
        return
    for value in values:
        st.caption(str(value))


def footer() -> None:
    """CFBD credit, on every page (AC-G.43), plus the author links."""
    st.markdown(
        f"<div class='cfdb-footer'>{CFBD_CREDIT}<br>"
        f"<span class='cfdb-footer-links'>Built by Marc Alexander · {AUTHOR_LINKS}</span>"
        f"</div>", unsafe_allow_html=True)
