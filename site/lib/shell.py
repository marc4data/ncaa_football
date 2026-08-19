"""The page shell every page renders through.

Exists so the Part 0 contract is applied once rather than eighteen times. A page that
forgets its readiness line, its Degraded sections or its CFBD footer is not possible if the
shell owns them — which is the difference between a consistent site and eighteen
inconsistent ones.
"""
from typing import Callable, Optional

import streamlit as st

from lib import attribution, states
from lib.registry import BY_KEY, Page


def header(page: Page) -> None:
    st.title(page.title)
    st.markdown(f"<div class='cfdb-readiness'>{page.readiness}"
                + (f" · reads <code>{page.view}</code>" if page.view else "")
                + "</div>", unsafe_allow_html=True)


def blocked(page: Page) -> None:
    """A page whose primary view does not exist. Visible in nav, honest on screen."""
    states.degraded(page.blocker or (page.view or "its primary view"),
                    page.blocker_note or "This page's primary view has not been built yet.",
                    scheduled="after the other blocked pages")


def partial_notice(page: Page) -> None:
    """Sections that will render Degraded within an otherwise working page (AC-8.2)."""
    for section in page.partial_sections:
        states.degraded(section.split("(")[-1].rstrip(")") if "(" in section else section,
                        f"{section.split('(')[0].strip()} is not available yet.")


def render_page(key: str, body: Optional[Callable[[Page], None]] = None) -> None:
    """Standard page lifecycle: header, body or blocked state, attribution, footer."""
    page = BY_KEY[key]
    header(page)

    if not page.buildable:
        blocked(page)
    elif body is not None:
        body(page)
    else:
        states.degraded(page.view or "this page",
                        "The data for this page is ready; the page itself is not built yet.",
                        scheduled="A4 — build the 18 pages")

    if page.partial_sections and page.buildable:
        st.divider()
        st.caption("Sections not yet available on this page:")
        partial_notice(page)

    attribution.footer()
