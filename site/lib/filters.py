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
    df = query("select distinct season from srv_game order by season desc limit 200")
    return df["season"].tolist()


@st.cache_data(ttl=3600)
def _weeks(season: int, season_type: str) -> list:
    df = query("""select distinct week from srv_game
                  where season = :season and season_type = :season_type
                  order by week limit 40""",
               {"season": season, "season_type": season_type})
    return df["week"].tolist()


# R-165. THE CACHE KEY CARRIES `division` BECAUSE THE RESULT NOW DEPENDS ON IT.
# A key that misses a dependency is a stale option list, and a stale option list looks like a
# data bug and gets debugged as one.
@st.cache_data(ttl=3600)
def _conferences(season: int, division: str = "all") -> list:
    """The conferences that actually appear in a season, narrowed by division.

    HOME AND AWAY, NOT HOME ONLY. The previous query read `home_conference` alone, so a
    conference whose members never hosted in a season was simply missing from the filter — a
    silent omission rather than an empty result. Pre-existing, two lines to fix, and this is
    the query that fixes it.

    ONE RELATION, ONE PASS (G-2). The two sides are unioned inside a single scan of srv_game
    rather than joined, because the app is not allowed to join and does not need to: a
    conference is present if it appears on either side of any game.

    `division` is the filter bar's own value — 'fbs' means "either team is FBS", matching the
    spine rule the pages use, and 'all' means no narrowing at all.
    """
    # TWO QUERIES, NOT A UNION, AND THE CONTRACT IS RIGHT TO INSIST.
    #
    # The first version wrote this as one `union all` over the two sides. `check_contract`
    # rejected it — G-2 is one relation per query, and `union` is in the forbidden list — and
    # the rule earns its keep here: a union inside the app is the shape that becomes a join
    # inside the app. Two compliant reads of the same relation, combined in Python, is not
    # metric arithmetic; it is deduplicating a list of names.
    both = set()
    for side in ("home", "away"):
        df = query(f"""
            select distinct {side}_conference as conference
            from srv_game
            where season = :season
              and {side}_conference is not null
              and (:division = 'all' or is_fbs_game)
            order by conference
            limit 200
        """, {"season": season, "division": division})
        both.update(df["conference"].tolist())
    return sorted(both)


def resolve_conference(current, options: list):
    """R-165. Does the incoming conference survive the current division? (value, dropped).

    ONE RULE FOR TWO ENTRY POINTS, DELIBERATELY. A conference can stop being valid because the
    reader changed Division, or because they arrived on `?division=fbs&conference=Big+Sky`
    from a bookmark or from a link built before the cascade existed. Both land here, so a
    bookmark cannot behave differently from a click — which is the property AC-G.13 needs,
    since scope travels in query params by design.

    Falling back to All rather than 404ing or serving a filter that disagrees with the URL:
    the reader asked for a narrower view than exists, and the honest answer is the wider one
    plus a notice. `dropped` is what makes the notice possible — a filter that changes itself
    silently is R-010/R-011 again.
    """
    if not current or current in options:
        return current, None
    return None, current


def game_scope(show_week: bool = True, show_conference: bool = True,
               show_season: bool = True, week_note: str = "",
               conference_note: str = "", season_note: str = "") -> GameScope:
    """The global filter bar, rendered at the top of EVERY data page.

    Every value is read from the URL first and written back after, so the scope survives a
    page change. Nothing here mutates session state — AC-G.13 requires navigation by query
    params, and a filter held only in session is a filter that cannot be linked to.

    F2-01 was still broken after the last pass because only SIX of eighteen pages called
    this at all. Rankings, Stats, Today, Odds, Line Movement, Edge Finder, Model Performance
    and the Team page each rolled their own selectors, so they neither read the incoming
    scope nor wrote it back — the scope did not "drop on some routes", it was never on them.

    F2-03: an inapplicable filter is DISABLED WITH A REASON, never absent. Teams is
    team-by-season grain so a week means nothing there, but its absence is what made the
    page feel broken. Consistency of chrome beats per-page optimisation, and a disabled
    control with a tooltip answers the question the missing one raised.
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
    current_conf = params.get("conference")
    division_labels = list(DIVISIONS)
    current_division = params.get("division") or DEFAULT_DIVISION
    division_label = next((k for k, v in DIVISIONS.items() if v == current_division),
                          division_labels[0])

    # A horizontal row under the title. Columns rather than the sidebar, per the amendment.
    # Always five slots. A bar that changes shape per page is a bar the reader has to
    # re-learn, and a missing control reads as a missing feature.
    # R-158 BAND 2: the five filters, the state chip and the Reset button on ONE row. The
    # chip and the button are both about the filter state and cost two further full-width rows
    # to say so. The last two slots are narrow because they hold a chip and a button, not a
    # control.
    slots = st.columns([1.05, 0.95, 1.0, 1.15, 1.5, 1.7, 1.1], vertical_alignment="bottom")
    index = 0

    with slots[index]:
        # A disabled season still SHOWS the inherited value, so a page that cannot scope by
        # season says so rather than looking like it forgot.
        season = st.selectbox("Season", seasons, index=seasons.index(season),
                              key="flt_season", disabled=not show_season,
                              help=season_note or None)
    index += 1
    with slots[index]:
        season_type = st.selectbox(
            "Type", ["regular", "postseason"],
            index=0 if season_type == "regular" else 1, key="flt_type")
    index += 1
    with slots[index]:
        week_choice = st.selectbox(
            "Week", week_options if show_week else ["All"],
            index=week_options.index(current_week)
            if show_week and current_week in week_options else 0,
            key="flt_week", disabled=not show_week,
            help=week_note or None)
        if not show_week:
            week_choice = "All"
    index += 1
    # R-165. DIVISION IS DECLARED BEFORE CONFERENCE, WHICH IS THE WHOLE IMPLEMENTATION.
    #
    # Marc's first instinct was Conference on the far left; he corrected it to far right, and
    # the correction is what makes this simple. A cascading control has to be read before the
    # list it controls can be computed, so declaration order and visual order now agree and no
    # out-of-order column machinery is needed.
    #
    # Two chains, each with its controller first:  WHEN season -> type -> week
    #                                              WHO  division -> conference
    with slots[index]:
        division_label = st.selectbox(
            "Division", division_labels, index=division_labels.index(division_label),
            key="flt_div",
            help="FBS by default. A game counts as FBS if EITHER team is FBS, so a "
                 "non-FBS visitor's trip to an FBS stadium is included.")
    index += 1
    division = DIVISIONS[division_label]
    conferences = ["All"] + _conferences(season, division)

    # R-165. A CONFERENCE THAT IS NO LONGER AN OPTION FALLS BACK TO ALL, AND SAYS SO.
    #
    # Switching Division from All to FBS with "Big Sky" selected leaves a value that is not in
    # the new list. Streamlit would silently reset the widget to index 0, which is the same
    # class of defect as R-010/R-011 — filter state changing without telling anyone.
    #
    # THE URL HALF IS THE SAME CODE PATH, DELIBERATELY. `?division=fbs&conference=Big+Sky` is
    # reachable from a bookmark or from a link built before this change, and it resolves here
    # exactly as an in-session switch does: to All, with the notice shown. One rule, so a
    # bookmark cannot behave differently from a click.
    dropped_conference = None
    if show_conference:
        current_conf, dropped_conference = resolve_conference(current_conf, conferences)

    with slots[index]:
        conference = st.selectbox(
            "Conference", conferences if show_conference else ["All"],
            index=conferences.index(current_conf)
            if show_conference and current_conf in conferences else 0,
            key="flt_conf", disabled=not show_conference,
            help=conference_note or None)
        if not show_conference:
            conference = "All"

    week = None if week_choice == "All" else int(week_choice)
    conf = None if conference == "All" else conference

    # Written back on every render, which is what makes the scope survive a page change.
    params.set_params(
        season=season, week=week, conference=conf, division=division,
        season_type=None if season_type == "regular" else season_type)

    scope = GameScope(season, week, season_type, conf, division)
    _summary(scope, seasons[0] if seasons else season, slots[5], slots[6])
    if dropped_conference:
        st.warning(
            f"**{dropped_conference}** is not in {division_label}, so the conference filter "
            f"was cleared. Pick another, or widen Division.", icon=":material/filter_alt:")
    return scope


def _summary(scope: GameScope, newest_season: int, chip_slot, reset_slot) -> None:
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

    # R-158 BAND 2. The chip and the button now render INTO the filter row's last two slots
    # rather than onto two more full-width rows of their own. They describe the controls
    # immediately to their left, which is where a reader looks for them.
    if not off_default:
        with chip_slot:
            st.markdown(
                f"<div class='cfdb-scope'>Season <strong>{scope.season}</strong>, "
                f"all weeks, FBS.</div>", unsafe_allow_html=True)
        return

    chips = "".join(f"<span class='cfdb-scope-chip'>{value}</span>" for value in off_default)
    with chip_slot:
        st.markdown(
            f"<div class='cfdb-scope cfdb-scope-active'>Filtered: {chips}</div>",
            unsafe_allow_html=True)
    # One click back to the default state, present only when there is something to reset —
    # a permanently visible reset button is noise on the page it is least needed.
    with reset_slot:
        if st.button(f"Reset to {newest_season}", key="flt_reset",
                     help=f"Clear every filter and return to Season {newest_season}."):
            params.set_params(season=None, week=None, conference=None, division=None,
                              season_type=None)
            st.rerun()


def clear() -> None:
    """AC-G.17: clearing returns to the DEFAULT state, not to an empty one."""
    for key in ("week", "conference"):
        params.set_params(**{key: None})
    st.rerun()
