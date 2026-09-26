"""The page shell every page renders through.

Exists so the Part 0 contract is applied once rather than eighteen times. A page that
forgets its readiness line, its Degraded sections or its CFBD footer is not possible if the
shell owns them — which is the difference between a consistent site and eighteen
inconsistent ones.
"""
from typing import Callable, Optional

import streamlit as st

from lib import attribution, params, states
from lib.registry import BY_KEY, Page


# R-158 BAND 1. The as-of stamp belongs beside the status, but it is not known until the page
# has queried — and `render_page` calls `header()` before `body()`. A placeholder reserves the
# spot; `table.as_of_caption` fills it if one is waiting and falls back to its own caption if
# not, so the seventeen pages that have not been reorganised keep working unchanged.
_ASOF_SLOT = None


def as_of_slot():
    """The Band 1 placeholder, or None on a page that has not reserved one."""
    return _ASOF_SLOT


# 🚨 A243 (cfdb-main-R-3328). ONE `Dataset:` LINE PER TAB, BUILT FROM THE SECTIONS THEMSELVES.
#
# > **MARC, 2026-09-26:** *"why is there a singular standalone dataset line under the KPIs and
# > then 2 more dataset lines at the top of the page? … Consolidate instead of wasting 3 lines."*
#
# 📊 THE CAUSE: `states.section(dataset=…)` renders its caption BEFORE its `yield`, so every
# panel's line lands above that panel — and the line under the KPI row is the NEXT panel's.
# Measured on Looking Back before this: **eight** `cfdb-dataset` divs, `srv_game` twice.
#
# 🚨 AND THE OBVIOUS FIX IS THE ONE R-574 ALREADY PUNISHED: Today once carried a single
# hand-written `dataset_caption("Looking Back", "srv_game")` while reading FIVE views, and because
# the label links to `/dictionary?table=…`, a reader clicking it from the Leaderboards landed on
# the wrong table. **So this collects what the sections THEMSELVES declare — no second list to
# drift** — and each name keeps its own link.
_DATASET_SLOT = None
_DATASETS_SEEN: list = []


def dataset_slot():
    """The tab's reserved `Dataset:` placeholder, or None when no tab reserved one."""
    return _DATASET_SLOT


def open_dataset_slot():
    """Reserve the line at the TOP of a tab and start collecting. Marc chose 1-B: the top."""
    global _DATASET_SLOT, _DATASETS_SEEN
    _DATASETS_SEEN = []
    _DATASET_SLOT = st.empty()
    return _DATASET_SLOT


def register_dataset(label: str, view: str) -> bool:
    """Record a `(label, view)` a section declared. True when the slot took it.

    ⚠️ DE-DUPLICATED ON THE PAIR, first-seen order — `srv_game` is read by more than one panel on
    Looking Back and must appear once.
    """
    if _DATASET_SLOT is None:
        return False
    if (label, view) not in _DATASETS_SEEN:
        _DATASETS_SEEN.append((label, view))
    return True


def close_dataset_slot() -> None:
    """Fill the reserved line with ONE caption naming every view the tab's sections declared.

    ⚠️ NOTHING REGISTERED RENDERS NOTHING — not `Dataset:` with an empty tail. AC-G.11: an absence
    must say which absence it is, and the honest absence here is silence.
    """
    global _DATASET_SLOT
    slot, seen = _DATASET_SLOT, list(_DATASETS_SEEN)
    _DATASET_SLOT = None
    if slot is None or not seen:
        return
    from lib import table
    first, rest = seen[0], seen[1:]
    with slot:
        table.dataset_caption(first[0], first[1], rest)


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


def discard_unreadable_params() -> list:
    """Read every known parameter once, drop the ones that cannot be read, and name them.

    🚨 A226 (cfdb-main-R-3057). A BAD PARAMETER USED TO TAKE THE WHOLE PAGE TO ZERO.
    `params.get` raises `BadParam` for a value it cannot type, and **nothing caught it for
    the four `INT_PARAMS`** — the raise escaped every `states.section`, so `?season=banana`,
    `?game_id=x` or a stale `?week=All` rendered no panels, no error card, nothing at all.
    A225 found it as a `week` problem; it is a FOUR-PARAMETER problem on any page that reads
    them, from any hand-typed or stale URL.

    ## Why the catch is HERE and not inside `params.get`

    ⚠️ A fallback inside `get` would fix all four parameters and every caller in one place —
    and it would make a raising function stop raising. `BadParam` would then have **no live
    raiser for an int**, and a bad value would become a default that the reader cannot
    distinguish from the default they asked for. **That is the "graceful fallback that fires
    100% of the time is indistinguishable from a design" shape this project has paid for
    twice** — the monogram that was drawn for every team, and R-299's left join that matched
    every row. The exception is the only thing that knows the difference.

    ✅ SO THE RAISE STAYS HONEST AND THE SHELL DECIDES WHAT TO DO WITH IT. One catch, before
    any page body runs, covering every page and every parameter — and the notice reaches the
    reader from OUTSIDE any panel, which is the only place it can be seen when the alternative
    is a page with no panels at all.

    ⚠️ IT RUNS BEFORE `body()`, NOT AROUND IT, AND THAT IS THE POINT. Wrapping the body would
    catch the raise halfway through a render and leave the reader a half-drawn page followed
    by a notice followed by a second copy. Reading the parameters first means the body never
    sees a value it cannot use.

    ⚠️ AND DROPPING A PARAMETER DOES NOT RE-RUN THE SCRIPT — `params.set_params` is already
    called on every render of every scoped page (its own docstring says so), which would loop
    forever if a write re-ran. So the notice and the clean render happen in the same pass.
    """
    bad = []
    for name in sorted(params.INT_PARAMS | set(params.ENUM_PARAMS)):
        try:
            params.get(name)
        except params.BadParam as exc:
            bad.append((exc.name, exc.value))
    for name, _value in bad:
        params.set_params(**{name: None})
    return bad


def render_page(key: str, body: Optional[Callable[[Page], None]] = None) -> None:
    """Standard page lifecycle: header, body or blocked state, attribution, footer."""
    page = BY_KEY[key]
    # 🚨 BEFORE THE HEADER, BECAUSE THE HEADER READS PARAMETERS TOO.
    discarded = discard_unreadable_params()
    header(page)
    if discarded:
        states.discarded(discarded)

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
