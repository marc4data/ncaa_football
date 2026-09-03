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


# R-158 BAND 1. The as-of stamp belongs beside the status, but it is not known until the page
# has queried — and `render_page` calls `header()` before `body()`. A placeholder reserves the
# spot; `table.as_of_caption` fills it if one is waiting and falls back to its own caption if
# not, so the seventeen pages that have not been reorganised keep working unchanged.
_ASOF_SLOT = None


def as_of_slot():
    """The Band 1 placeholder, or None on a page that has not reserved one."""
    return _ASOF_SLOT


def header(page: Page) -> None:
    """R-158 BAND 1: title left; readiness and the as-of stamp right, on the title's line.

    Marc: "The first row of games is in the bottom 20% of the page." Measured on the deployed
    site before this: the first card sat at y=690 on a 1000px viewport, with nineteen blocks
    above it, eleven of them full-width rows carrying one short line each. The title, the
    status line and the as-of stamp were three of those rows and together they say one thing —
    what this page is and how fresh it is.
    """
    global _ASOF_SLOT
    # 5:4 rather than 3:2: at 1200 the narrower column wrapped `reads srv_game` onto a
    # second line, which put the as-of stamp back where R-158 moved it from.
    left, right = st.columns([5, 4], vertical_alignment="bottom")
    with left:
        st.title(page.title)
    with right:
        st.markdown(f"<div class='cfdb-readiness cfdb-readiness-right'>{page.readiness}"
                    + (f" · reads <code>{page.view}</code>" if page.view else "")
                    + "</div>", unsafe_allow_html=True)
        _ASOF_SLOT = st.empty()


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
