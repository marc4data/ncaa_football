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
CFBD_CREDIT = (
    'Data sourced from the '
    '<a href="https://collegefootballdata.com" target="_blank" rel="noopener">'
    'CollegeFootballData API</a>. Attribution is optional under their terms; '
    'cfdb provides it anyway.')

# This site is a portfolio piece, so the links are part of the point rather than an
# afterthought bolted to the bottom.
AUTHOR_LINKS = (
    '<a href="https://www.linkedin.com/in/marc4data/" target="_blank" rel="noopener">'
    'LinkedIn</a> · '
    '<a href="https://marc4data.netlify.app/" target="_blank" rel="noopener">'
    'marc4data.netlify.app</a>')


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
