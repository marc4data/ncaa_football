"""The four states every data-bearing section is in, and never any other.

Loading / Empty / Degraded / Error, per AC-G.5 to AC-G.9.

The distinction the whole module exists for is Empty versus Degraded. "No games match your
filters" and "the rankings table has not been built" are opposite claims — one is the user's
doing and one is ours — and if both render as a blank panel the site has told the user
nothing while looking like it answered. Empty offers the control that fixes it; Degraded
names the missing object in code font so the blocker can be read off the screen.
"""
from contextlib import contextmanager
from typing import Callable, Optional

import pandas as pd
import streamlit as st


def loading(height_rows: int = 8, columns: int = 4) -> None:
    """A skeleton at the LOADED content's dimensions, not a spinner (AC-G.8).

    A spinner collapses the layout and the page jumps when data arrives; a skeleton the
    same height as the real table means the page never moves.
    """
    st.markdown(
        f"<div class='cfdb-skel' style='height:{height_rows * 2.1 + 2.4:.1f}rem'>"
        + "".join("<div class='cfdb-skel-row'></div>" for _ in range(height_rows))
        + "</div>",
        unsafe_allow_html=True,
    )


def empty(what: str, why: str, fix_label: Optional[str] = None,
          fix: Optional[Callable[[], None]] = None) -> None:
    """Query succeeded, zero rows. The user's filters, not our pipeline.

    Always says what would be here and why it is not, and offers the control most likely to
    resolve it — an Empty state with no way forward is a dead end.
    """
    st.markdown(
        f"<div class='cfdb-state cfdb-empty'>"
        f"<div class='cfdb-state-title'>Nothing to show</div>"
        f"<div class='cfdb-state-body'>{what} {why}</div></div>",
        unsafe_allow_html=True,
    )
    if fix_label and fix:
        if st.button(fix_label, key=f"fix_{abs(hash(what + fix_label))}"):
            fix()


def degraded(missing_object: str, explanation: str, scheduled: Optional[str] = None) -> None:
    """The section's source does not exist yet. Ours, not the user's.

    Names the object in code font (AC-G.7). The rest of the page renders normally — a
    blocked section must not blank a working page.
    """
    sched = (f"<div class='cfdb-state-note'>Scheduled: {scheduled}</div>" if scheduled else "")
    st.markdown(
        f"<div class='cfdb-state cfdb-degraded'>"
        f"<div class='cfdb-state-title'>Not built yet</div>"
        f"<div class='cfdb-state-body'>{explanation}</div>"
        f"<div class='cfdb-state-object'>Waiting on <code>{missing_object}</code></div>"
        f"{sched}</div>",
        unsafe_allow_html=True,
    )


def error(view: str, retry: Optional[Callable[[], None]] = None) -> None:
    """The query raised. Plain language, the view name, a retry — never a traceback.

    AC-G.9: no traceback, no connection string, no host, no credential. A user who can see
    a stack trace can see the database host, and this site is a portfolio piece.
    """
    st.markdown(
        f"<div class='cfdb-state cfdb-error'>"
        f"<div class='cfdb-state-title'>Could not load this section</div>"
        f"<div class='cfdb-state-body'>Something went wrong reading "
        f"<code>{view}</code>. This is our problem, not yours.</div></div>",
        unsafe_allow_html=True,
    )
    if retry and st.button("Try again", key=f"retry_{abs(hash(view))}"):
        retry()


@contextmanager
def section(view: str, degraded_if_missing: Optional[str] = None,
            explanation: str = "", scheduled: Optional[str] = None):
    """Wrap a section so an exception becomes an Error state instead of a broken page.

    `degraded_if_missing` distinguishes the two failure modes that look alike from inside a
    try block: a missing relation is Degraded (we have not built it), anything else is Error
    (it exists and something went wrong).
    """
    try:
        yield
    except Exception as exc:                                   # noqa: BLE001
        message = str(exc).lower()
        missing = ("does not exist" in message or "not found" in message
                   or "undefined table" in message)
        if missing and degraded_if_missing:
            degraded(degraded_if_missing, explanation or
                     "This section's data has not been built yet.", scheduled)
        else:
            error(view)


def render_or_state(df: pd.DataFrame, view: str, what: str, why: str,
                    renderer: Callable[[pd.DataFrame], None],
                    fix_label: Optional[str] = None,
                    fix: Optional[Callable[[], None]] = None) -> None:
    """Render the frame, or the Empty state — never a zero-row table.

    AC-G.6: a page must not show `0`, an em dash or an empty table where the honest answer
    is "nothing matched" or "not built yet".
    """
    if df is None or df.empty:
        empty(what, why, fix_label, fix)
        return
    renderer(df)
