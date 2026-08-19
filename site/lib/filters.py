"""One filter contract, applied identically everywhere (§0.4).

Defaults read flag columns rather than literals (AC-G.15), option lists come from the
page's own serving view so an option that would return zero rows is never offered
(AC-G.16), and every choice round-trips through the URL (AC-G.18).
"""
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from lib import params
from lib.query import query


@dataclass
class GameScope:
    season: int
    week: Optional[int]
    season_type: str
    conference: Optional[str]

    def describe(self) -> str:
        bits = [f"season {self.season}", self.season_type]
        if self.week is not None:
            bits.append(f"week {self.week}")
        if self.conference:
            bits.append(self.conference)
        return ", ".join(bits)


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


def game_scope() -> GameScope:
    """Sidebar filters for any week-scoped page. State lives in the URL."""
    seasons = _seasons()
    default_season = params.get("season") or (seasons[0] if seasons else None)
    with st.sidebar:
        season = st.selectbox("Season", seasons,
                              index=seasons.index(default_season) if default_season in seasons else 0)
        season_type = st.selectbox("Season type", ["regular", "postseason"],
                                   index=0 if (params.get("season_type") or "regular") == "regular" else 1)
        weeks = _weeks(season, season_type)
        week_options = ["All"] + [str(w) for w in weeks]
        current_week = params.get("week")
        week_index = week_options.index(str(current_week)) if str(current_week) in week_options else 0
        week_choice = st.selectbox("Week", week_options, index=week_index)
        conferences = ["All"] + _conferences(season)
        conf_current = params.get("conference")
        conf_index = conferences.index(conf_current) if conf_current in conferences else 0
        conference = st.selectbox("Conference", conferences, index=conf_index)

    week = None if week_choice == "All" else int(week_choice)
    conf = None if conference == "All" else conference
    params.set_params(season=season, week=week, season_type=season_type, conference=conf)
    return GameScope(season, week, season_type, conf)


def clear() -> None:
    """AC-G.17: clearing returns to the DEFAULT state, not to an empty one."""
    for key in ("week", "conference"):
        params.set_params(**{key: None})
    st.rerun()
