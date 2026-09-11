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

import os
import sys

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


def degraded(missing_object: str, explanation: str, scheduled: Optional[str] = None,
             title: str = "Not built yet") -> None:
    """The section cannot render because something upstream is absent. Ours, not the user's.

    Names the object in code font (AC-G.7). The rest of the page renders normally — a
    blocked section must not blank a working page.

    ⚠️ `title` EXISTS BECAUSE "Not built yet" IS FALSE FOR THREE OF THE EIGHT CALLERS, AND IT
    CONTRADICTS THEIR OWN EXPLANATION ON THE SAME CARD. R-500.

    B074 found it on Matchup: srv_team_week IS built and IS published — it is that team's ROW
    that is absent — and the body says so while the title says the opposite. B correctly
    refused to fix it, because this module is imported by every data-bearing section on the
    site and changing its copy from a session that owns one page changes eighteen.

    Reading all eight call sites first turned up two more of the same shape, which is why
    this is a parameter rather than a new hardcoded string:

        standings.py:51  "The ratings themselves are built — see any team's Ratings tab —
                          but they are not yet carried as columns here"
        team.py:90       "The data for this is now in the warehouse: fct_team_rating_week
                          carries a pregame and postgame Elo per team per week"

    Both describe something BUILT and not yet surfaced. Titling that "Not built yet" tells a
    reader the opposite of the sentence directly beneath it.

    ⚠️ THE DEFAULT IS UNCHANGED ON PURPOSE. Five callers are genuinely about an object that
    does not exist — shell.py's three, team.py:72's dim_athlete, and section()'s automatic
    path, which fires only on "does not exist" / "undefined table". A single title honest for
    all eight does not exist, because "we have not built it", "we built it and have not
    surfaced it here" and "it exists and this row is absent" are three different claims. So
    the callers that need a different one say so, and nobody else moves.
    """
    sched = (f"<div class='cfdb-state-note'>Scheduled: {scheduled}</div>" if scheduled else "")
    st.markdown(
        f"<div class='cfdb-state cfdb-degraded'>"
        f"<div class='cfdb-state-title'>{title}</div>"
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


def render_failed() -> None:
    """R-630. The data arrived and the page could not draw it.

    ⚠️ IT NAMES NO INTERNAL, AND THAT IS THE POINT. A view name here would be the A086 defect
    restated: the query succeeded, so the view is not what failed, and printing it sends the
    next reader — or the next round — to the wrong layer. AC-G.9 still holds absolutely: no
    traceback, no host, no credential, no exception text.

    ⚠️ IT KEEPS THE PHRASE "Something went wrong", AND THAT IS DELIBERATE RATHER THAN INHERITED.
    `test_a_broken_row_degrades_this_panel_and_not_the_page` in tests/test_matchup_yardage.py
    asserts that phrase, and that file is session B's (§3). A shared-module change ships the new
    behaviour and holds the other session's page harmless — the same call A085 made for
    fmt.PRECISION rather than reaching into B's file. The sentence is honest either way: what
    went wrong is the BUILDING, and the clause says so.
    """
    st.markdown(
        "<div class='cfdb-state cfdb-error'>"
        "<div class='cfdb-state-title'>Could not display this section</div>"
        "<div class='cfdb-state-body'>Something went wrong building this view after the data "
        "loaded. This is our problem, not yours.</div></div>",
        unsafe_allow_html=True,
    )


def _trace(exc: BaseException, view: str) -> None:
    """⚠️ THE OPERATOR'S HALF OF R-630, AND IT IS OFF BY DEFAULT.

    B084 had to patch `states.section` to a passthrough to discover that its Error state was a
    dropped SSH tunnel. A session rendering a page needs the real exception WITHOUT editing the
    page, and four of R-571's five cases would have been a one-line diagnosis with this on.

    🚨 STDERR, NEVER THE PAGE. The reader's screen is not the channel — that is AC-G.9 and it is
    absolute. Enabled with CFDB_TRACE_STATES=1, which nothing in production sets.

    Type, message and the FAILING LINE — the last frame inside site/, which is the line a
    session actually needs and is not the line the exception was caught on.
    """
    if os.environ.get("CFDB_TRACE_STATES") != "1":
        return
    where = ""
    frame = exc.__traceback__
    while frame is not None:
        name = frame.tb_frame.f_code.co_filename
        if "/site/" in name:
            where = f"{name.split('/site/')[-1]}:{frame.tb_lineno}"
        frame = frame.tb_next
    print(f"[states.section {view}] {type(exc).__name__}: {exc}"
          + (f"  at {where}" if where else ""), file=sys.stderr)


@contextmanager
def section(view: str, degraded_if_missing: Optional[str] = None,
            explanation: str = "", scheduled: Optional[str] = None,
            dataset: Optional[str] = None):
    """Wrap a section so an exception becomes an Error state instead of a broken page.

    `degraded_if_missing` distinguishes the two failure modes that look alike from inside a
    try block: a missing relation is Degraded (we have not built it), anything else is Error
    (it exists and something went wrong).

    ⚠️ R-574. `dataset` RENDERS THE READER-FACING CAPTION FROM THE SAME ARGUMENT THAT NAMES
    THE VIEW, AND THAT IS THE ENTIRE POINT OF PUTTING IT HERE.

    Today carried one `table.dataset_caption("Looking Back", "srv_game")` at the top of the
    page while reading FIVE views, so the caption was wrong for four of six sections — and
    because it renders a link to /dictionary?table=..., a reader clicking it from the
    Leaderboards landed on the wrong table. The right answer was already in the file and only
    ever visible when something broke: every panel already names its own view HERE, in the
    error path.

    So the caption is emitted from this argument rather than from a second panel-to-view list
    beside it. Two lists drift; that is what ci/check_publish_build_agreement.py exists to
    prevent one layer down, and R-574 is the same shape at page grain. A caption that
    disagrees with the Error state under the same panel is now impossible to write.

    `view` is the IDENTIFIER and stays the identifier — it is what the Degraded state prints
    and what the dictionary link filters on. `dataset` is the LABEL and is editorial: front
    of house says "Team box scores", never `srv_team_game_log` (AC-G.7, as amended).

    Omitting `dataset` renders nothing, so the other nineteen view modules are unaffected.
    """
    if dataset:
        # Deferred, matching table.as_of_caption's own import of shell: lib.table imports
        # four sibling modules and this one imports none, so keeping the edge out of module
        # scope keeps that asymmetry from becoming a cycle later.
        from lib import table
        table.dataset_caption(dataset, view)
    from lib.query import QueryFailed
    try:
        yield
    except QueryFailed as exc:
        # 🚨 R-630. THE QUERY RAISED, SO THE VIEW NAME IS HONEST AND `error()` MAY PRINT IT.
        _trace(exc.original, view)
        message = str(exc.original).lower()
        missing = ("does not exist" in message or "not found" in message
                   or "undefined table" in message)
        if missing and degraded_if_missing:
            degraded(degraded_if_missing, explanation or
                     "This section's data has not been built yet.", scheduled)
        else:
            error(view)
    except Exception as exc:                                   # noqa: BLE001
        # 🚨 R-630. ANYTHING ELSE RAISED, WHICH MEANS THE QUERY SUCCEEDED AND THE PAGE FAILED.
        #
        # ⚠️ IT MUST NOT NAME THE VIEW. A086: this branch reported "something went wrong reading
        # srv_rankings" while srv_rankings was returning 101 healthy rows — the fault was an
        # AttributeError in the renderer, and the message pointed a whole round at the data
        # layer. The old code could not tell the two apart because it caught one exception type
        # and named whatever argument it had been given.
        _trace(exc, view)
        render_failed()


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
