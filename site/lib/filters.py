"""One filter contract, applied identically everywhere (§0.4, amended).

TWO CHANGES FROM THE ORIGINAL, both from walking the site rather than reading it.

FILTERS ARE AT THE TOP, NOT IN THE SIDEBAR. The requirement said sidebar; every sports site
puts season and week controls above the content because that is where the eye lands, and
the sidebar is navigation. A control the reader has to go looking for is a control they
assume is not there.

FILTERS SURVIVE NAVIGATION. This is the one that made the site feel broken: choosing season
2025 to see results, moving to another page, and being silently returned to 2026. The cause
was that each page read `params.get("season")` and fell back to its own default whenever the
URL happened not to carry one — so the filter round-tripped within a page and evaporated
between them.

The fix is that the scope is written to the URL on every render and read back on the next,
and every internal link carries it forward. AC-G.18 asked for round-tripping; what was
missing is that a link is part of the trip.

Option lists still come from the page's own serving view, so an option that would return
zero rows is never offered (AC-G.16).
"""
from dataclasses import dataclass
from typing import List, Optional

import streamlit as st

from lib import params
from lib.query import query

# FBS spine (Marc, 2026-08-20). The site is about FBS; non-FBS teams exist as opponents with
# names, colours and slugs, and do not get index rows, standings rows or team pages.
#
# A DEFAULT, not a hardcoded WHERE. The whole point of a division filter is that someone can
# widen it, and a rule baked into every query is a rule nobody can see or change.
DIVISIONS = {
    "FBS": "fbs",
    "FBS + FCS": "fcs",
    "All divisions": "all",
}
DEFAULT_DIVISION = "fbs"


@dataclass
class GameScope:
    season: int
    week: Optional[int]
    season_type: str
    conference: Optional[str]
    division: str = DEFAULT_DIVISION

    def describe(self) -> str:
        bits = [f"season {self.season}", self.season_type]
        if self.week is not None:
            bits.append(f"week {self.week}")
        if self.conference:
            bits.append(self.conference)
        if self.division != "all":
            bits.append(self.division.upper())
        return ", ".join(bits)

    @property
    def classifications(self) -> List[str]:
        """Which classifications a query should accept.

        The inclusion rule for GAMES is EITHER team FBS, not both — a Division II visitor's
        trip to an FBS stadium is an FBS game. That is enforced in the serving views, which
        is where a rule that spans two columns belongs; this list is for team-grain pages.
        """
        if self.division == "all":
            return ["fbs", "fcs", "ii", "iii", "ii/iii"]
        if self.division == "fcs":
            return ["fbs", "fcs"]
        return ["fbs"]

    def link(self, page: str, **extra) -> str:
        """An internal link that CARRIES THE SCOPE FORWARD.

        This is what makes filters persist. A link that drops the season is why choosing
        2025 and clicking a team returned a 2026 page.
        """
        carried = {"season": self.season, "week": self.week,
                   "season_type": None if self.season_type == "regular" else self.season_type,
                   "conference": self.conference,
                   "division": None if self.division == DEFAULT_DIVISION else self.division}
        carried.update(extra)
        return params.link(page, **carried)


@st.cache_data(ttl=3600)
def _seasons() -> list:
    df = query("select distinct season from srv_schedule order by season desc limit 200")
    return df["season"].tolist()


@st.cache_data(ttl=3600)
def _weeks(season: int, season_type: str) -> list:
    df = query("""select distinct week from srv_schedule
                  where season = :season and season_type = :season_type
                  order by week limit 40""",
               {"season": season, "season_type": season_type})
    return df["week"].tolist()


@st.cache_data(ttl=3600)
def _conferences(season: int) -> list:
    df = query("""select distinct home_conference as conference from srv_schedule
                  where season = :season and home_conference is not null
                  order by conference limit 60""", {"season": season})
    return df["conference"].tolist()


def game_scope(show_week: bool = True, show_conference: bool = True) -> GameScope:
    """The global filter bar, rendered at the top of the page.

    Every value is read from the URL first and written back after, so the scope survives a
    page change. Nothing here mutates session state — AC-G.13 requires navigation by query
    params, and a filter held only in session is a filter that cannot be linked to.
    """
    seasons = _seasons()
    if not seasons:
        return GameScope(0, None, "regular", None)

    requested = params.get("season")
    season = requested if requested in seasons else seasons[0]
    season_type = params.get("season_type") or "regular"

    weeks = _weeks(season, season_type)
    week_options = ["All"] + [str(w) for w in weeks]
    current_week = str(params.get("week"))
    conferences = ["All"] + _conferences(season)
    current_conf = params.get("conference")
    division_labels = list(DIVISIONS)
    current_division = params.get("division") or DEFAULT_DIVISION
    division_label = next((k for k, v in DIVISIONS.items() if v == current_division),
                          division_labels[0])

    # A horizontal row under the title. Columns rather than the sidebar, per the amendment.
    widths = [1.1, 1.0, 1.2, 1.5, 0.9]
    slots = st.columns(widths if show_conference else widths[:3] + widths[4:])
    index = 0

    with slots[index]:
        season = st.selectbox("Season", seasons, index=seasons.index(season),
                              key="flt_season")
    index += 1
    with slots[index]:
        season_type = st.selectbox(
            "Type", ["regular", "postseason"],
            index=0 if season_type == "regular" else 1, key="flt_type")
    index += 1
    with slots[index]:
        if show_week:
            week_choice = st.selectbox(
                "Week", week_options,
                index=week_options.index(current_week) if current_week in week_options else 0,
                key="flt_week")
        else:
            week_choice = "All"
    index += 1
    if show_conference:
        with slots[index]:
            conference = st.selectbox(
                "Conference", conferences,
                index=conferences.index(current_conf) if current_conf in conferences else 0,
                key="flt_conf")
        index += 1
    else:
        conference = "All"
    with slots[index]:
        division_label = st.selectbox(
            "Division", division_labels, index=division_labels.index(division_label),
            key="flt_div",
            help="FBS by default. A game counts as FBS if EITHER team is FBS, so a "
                 "non-FBS visitor's trip to an FBS stadium is included.")

    week = None if week_choice == "All" else int(week_choice)
    conf = None if conference == "All" else conference
    division = DIVISIONS[division_label]

    # Written back on every render, which is what makes the scope survive a page change.
    params.set_params(
        season=season, week=week, conference=conf, division=division,
        season_type=None if season_type == "regular" else season_type)

    scope = GameScope(season, week, season_type, conf, division)
    _summary(scope, seasons[0] if seasons else season)
    return scope


def _summary(scope: GameScope, newest_season: int) -> None:
    """AC-G.18b: the filter is VISIBLE STATE, and anything off-default is marked.

    Persisting silently is worse than not persisting at all. Not persisting was a bug you
    noticed immediately — choose 2025, navigate, get 2026 back. Persisting invisibly is a
    way to be confidently wrong: land on Stats, read 2025 numbers, and take them as
    current. A filter carried between pages has to announce itself on arrival.

    Off-default is marked rather than merely present, because "season 2025" reads as
    information and a highlighted "season 2025 · not current" reads as a state you are in.
    """
    off_default = []
    if scope.season != newest_season:
        off_default.append(f"Season {scope.season}")
    if scope.week is not None:
        off_default.append(f"Week {scope.week}")
    if scope.season_type != "regular":
        off_default.append(scope.season_type.title())
    if scope.conference:
        off_default.append(scope.conference)
    if scope.division != DEFAULT_DIVISION:
        off_default.append(next(k for k, v in DIVISIONS.items() if v == scope.division))

    if not off_default:
        st.markdown(
            f"<div class='cfdb-scope'>Showing <strong>Season {scope.season}</strong>, "
            f"all weeks, FBS.</div>", unsafe_allow_html=True)
        return

    chips = "".join(f"<span class='cfdb-scope-chip'>{value}</span>" for value in off_default)
    st.markdown(
        f"<div class='cfdb-scope cfdb-scope-active'>Filtered: {chips}</div>",
        unsafe_allow_html=True)
    # One click back to the default state, present only when there is something to reset —
    # a permanently visible reset button is noise on the page it is least needed.
    if st.button(f"Reset to Season {newest_season}", key="flt_reset"):
        params.set_params(season=None, week=None, conference=None, division=None,
                          season_type=None)
        st.rerun()


def clear() -> None:
    """AC-G.17: clearing returns to the DEFAULT state, not to an empty one."""
    for key in ("week", "conference"):
        params.set_params(**{key: None})
    st.rerun()
