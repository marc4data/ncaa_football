"""One table renderer, so eighteen pages format numbers the same way.

Formatting only. Every value arrives already computed — this decides how it looks, never
what it is (G-3). A column spec is declarative so a page says what a column MEANS and the
renderer decides precision, alignment and chip treatment from that.
"""
from typing import Callable, List, Optional

import pandas as pd
import streamlit as st

from lib import chips, fmt, identity


class Col:
    """One column: where it comes from, what it is, and how it should read."""

    def __init__(self, field: str, label: str, kind: str = "text",
                 dp: Optional[int] = None, width: Optional[str] = None,
                 render: Optional[Callable] = None):
        self.field, self.label, self.kind = field, label, kind
        self.dp, self.width, self.render = dp, width, render

    def format(self, row) -> str:
        if self.render is not None:
            return self.render(row)
        value = row.get(self.field)
        if self.kind == "num":
            return fmt.number(value, self.field, self.dp)
        if self.kind == "signed":
            return fmt.signed(value, self.field, self.dp)
        if self.kind == "datetime":
            return fmt.eastern(value)
        if self.kind == "cover":
            return chips.cover_chip_html(value)
        if self.kind == "bool":
            return chips.chip_html("y", "Yes") if value else chips.chip_html("n", "No")
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return fmt.EM_DASH
        return str(value)

    @property
    def css(self) -> str:
        return "cfdb-num" if self.kind in ("num", "signed") else ""


def render(df: pd.DataFrame, columns: List[Col], caption: str = "",
           link_builder: Optional[Callable] = None, max_rows: int = 300) -> None:
    """An HTML table, because Streamlit's dataframe cannot hold a chip or a link.

    AC-G.47: the table carries header semantics and a caption naming its source view.
    """
    head = "".join(f"<th class='{c.css}'>{c.label}</th>" for c in columns)
    body = []
    for _, row in df.head(max_rows).iterrows():
        cells = "".join(f"<td class='{c.css}'>{c.format(row)}</td>" for c in columns)
        href = link_builder(row) if link_builder else None
        attrs = f" onclick=\"window.location='{href}'\" style='cursor:pointer'" if href else ""
        body.append(f"<tr{attrs}>{cells}</tr>")
    st.markdown(
        "<table class='cfdb-table'>"
        + (f"<caption>{caption}</caption>" if caption else "")
        + f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>",
        unsafe_allow_html=True)
    if len(df) > max_rows:
        st.caption(f"Showing {max_rows:,} of {len(df):,} rows.")


def team_cell(row, slug_field: str, display_field: str, logo_field: str,
              rank_field: Optional[str] = None) -> str:
    """Logo-or-monogram plus name, with a rank badge only when the team is ranked.

    AC-1.5: an unranked team shows NO badge, not an em dash inside one.
    """
    logo = identity.logo_or_monogram(row.get(logo_field), row.get(display_field) or "?")
    rank = row.get(rank_field) if rank_field else None
    badge = (f"<span class='cfdb-rank'>#{int(rank)}</span>"
             if rank is not None and not pd.isna(rank) else "")
    return f"{logo}{badge}<span class='cfdb-team'>{row.get(display_field) or '—'}</span>"


def as_of_caption(df: pd.DataFrame) -> None:
    """AC-G.35: every page states when its own data was loaded."""
    if df is not None and not df.empty and "as_of_ts" in df.columns:
        st.caption(fmt.as_of(df["as_of_ts"].max()))
