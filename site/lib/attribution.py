"""Attribution, carried as data (§0.9, AC-G.41 to AC-G.44).

Sourced from the `attribution` COLUMN on the serving view, never from page config. That is
the whole design: a page physically cannot render the model's numbers without also having
fetched the string that says whose model it is.
"""
from typing import Optional

import pandas as pd
import streamlit as st

CFBD_CREDIT = ("Data from [CollegeFootballData.com](https://collegefootballdata.com). "
               "Optional under their terms; we do it anyway.")


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
    """CFBD credit, on every page (AC-G.43)."""
    st.markdown(f"<div class='cfdb-footer'>{CFBD_CREDIT}</div>", unsafe_allow_html=True)
