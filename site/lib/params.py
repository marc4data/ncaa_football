"""Deep links: the URL is the state (§0.3, AC-G.10 to AC-G.14).

One canonical name per concept, used everywhere. Per-page synonyms are how a bookmark stops
working, so the table below is the only place a parameter name is spelled.
"""
from typing import Any
from urllib.parse import quote

import streamlit as st

INT_PARAMS = {"season", "week", "game_id", "player_id"}
ENUM_PARAMS = {
    "season_type": {"regular", "postseason"},
    "division": {"fbs", "fcs", "all"},
    "market": {"spread", "total", "moneyline"},
    "stat_scope": {"team", "opponent"},
    "stat_basis": {"raw", "adjusted"},
    # Which end of the leaderboard leads. cfdb does not model whether a statistic is
    # better high or better low, so Stats asks rather than guesses, and the answer is part
    # of the URL like every other choice (AC-G.18) — a link to a leaderboard that arrives
    # sorted the other way is a link to a different claim.
    "order": {"desc", "asc"},
    # R-043. Which Schedule rendering is showing. THE REASON THE TAB IS A TAB: a tab is
    # URL-addressable and a toggle is not, and that is only true if the parameter is known
    # here. It was not, at first — unknown parameters are ignored silently (AC-G.11), so
    # ?view=stacked resolved to None, the radio fell back to its first option, and both
    # tabs rendered the dense table. The feature was inert and looked fine.
    "view": {"dense", "stacked"},
}
SLUG_PARAMS = {"team", "opponent", "conference", "poll", "provider", "model",
               "tab", "stat", "table",
               # The Players page: which athlete is selected, and the search term that found
               # them. Both were read without being registered, which meant link_here()
               # dropped them — so sorting or changing any filter on that page silently
               # deselected the player you were looking at.
               "player", "q",
               # Which column a table is sorted by. In the URL like every other choice, so
               # a sorted table can be linked to — AC-2.8 asks for sortable headers and
               # AC-G.18 decides where that state lives.
               "sort"}
KNOWN = INT_PARAMS | set(ENUM_PARAMS) | SLUG_PARAMS


class BadParam(Exception):
    """A known parameter with an out-of-range value.

    Distinct from an unknown parameter, which is ignored silently (AC-G.11). The difference
    matters: `?week=99` is a user asking for something that does not exist and deserves an
    Empty state naming the bad value; `?utm_source=x` is noise and deserves nothing.
    """

    def __init__(self, name: str, value: Any):
        self.name, self.value = name, value
        super().__init__(f"{name}={value}")


def get(name: str, default: Any = None) -> Any:
    """Read one parameter, typed. Raises BadParam for a known name with a bad value."""
    raw = st.query_params.get(name)
    if raw is None or raw == "":
        return default
    if name in INT_PARAMS:
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise BadParam(name, raw)
    if name in ENUM_PARAMS:
        if raw not in ENUM_PARAMS[name]:
            raise BadParam(name, raw)
        return raw
    return raw


def set_params(**kwargs) -> None:
    """Write parameters, dropping any set to None — and ONLY the ones that differ.

    AC-G.13: navigation happens by writing params, never by mutating session state alone —
    that is what makes a middle-click yield a working URL instead of the home page.

    ⚠ EVERY WRITE IS A HISTORY ENTRY, WHICH IS WHY THE FILTER IS NOT AN OPTIMISATION.
    Marc: "when I click out to a link (Matchup, Team) I have to hit the back button twice."

    Streamlit's frontend handles a Python-side query-param write with

        window.history.pushState({}, "", pathname + "?" + queryString)

    — a PUSH, not a replace. So a page that re-affirms what the URL already says still adds
    an entry, and Back then returns to the same page with the same parameters, which looks
    like the button not working.

    Two places do exactly that on arrival, measured rather than inferred: `matchup.py` writes
    `game_id` and `season` straight back (2 entries), and `filters.game_scope()` writes the
    whole scope on EVERY render of every scoped page (5). One click, several entries.

    Comparing first makes a re-affirmation free. A write that changes nothing was never
    navigation, and the URL is unchanged either way — so nothing about AC-G.13 is weakened:
    the parameter is still in the URL, still linkable, still middle-clickable. It simply is
    not announced twice.
    """
    changes = {}
    for key, value in kwargs.items():
        wanted = None if value is None else str(value)
        if st.query_params.get(key) != wanted:
            changes[key] = wanted
    for key, wanted in changes.items():
        if wanted is None:
            st.query_params.pop(key, None)
        else:
            st.query_params[key] = wanted


def link(page: str, **kwargs) -> str:
    """A URL for a page with parameters, for use in a clickable row."""
    query = "&".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    return f"/{page}?{query}" if query else f"/{page}"


def link_here(**overrides) -> str:
    """The CURRENT url with some parameters changed. For a sort toggle.

    Sorting must not throw away the scope. A header link that rebuilt the URL from scratch
    would drop the season and week the reader chose — which is exactly the bug that made
    filters feel broken, arriving by a different route.

    The page path comes from Streamlit rather than being passed in, so a header does not
    have to know which page it is on.
    """
    query = {k: v for k, v in st.query_params.items() if k in KNOWN}
    for key, value in overrides.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    encoded = "&".join(f"{k}={quote(str(v))}" for k, v in query.items())
    return f"?{encoded}" if encoded else "?"


def current() -> dict:
    """Every known parameter currently set, for cache keying (AC-G.36)."""
    return {k: v for k, v in st.query_params.items() if k in KNOWN}
