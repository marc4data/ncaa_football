"""Database access for the site.

Two rules this module exists to enforce:

1. **Read-only.** The site connects as `cfdb_read`, a role with SELECT and nothing else —
   verified at creation against INSERT/DELETE/CREATE/DROP. Serving is read-only by
   architecture, not by convention, so a bug in a page cannot write to the warehouse.
2. **Marts only.** Every query here selects from a `mart_*` table. If a page needs a number
   that isn't in a mart, the answer is a new dbt model, not a calculation here — the
   standing boundary, which matters most under schedule pressure.
"""
import os
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


@st.cache_resource
def engine():
    """One pooled engine per process; Streamlit reruns the script on every interaction."""
    user = os.getenv("CFDB_READ_USER", "cfdb_read")
    password = os.getenv("CFDB_READ_PASSWORD", "")
    host = os.getenv("SERVING_PG_HOST", os.getenv("PG_HOST", "localhost"))
    port = os.getenv("SERVING_PG_PORT", os.getenv("PG_PORT", "5432"))
    database = os.getenv("SERVING_PG_DB", os.getenv("PG_DB", "cfdb"))
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
                         pool_pre_ping=True)


@st.cache_data(ttl=600)
def query(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    with engine().connect() as connection:
        return pd.read_sql(text(sql), connection, params=params or {})


@st.cache_data(ttl=600)
def seasons() -> list:
    df = query("select distinct season from mart_team_schedule order by season desc")
    return df["season"].tolist()


@st.cache_data(ttl=600)
def teams_for_season(season: int) -> list:
    df = query("""
        select distinct team
        from mart_team_schedule
        where season = :season
        order by team
    """, {"season": season})
    return df["team"].tolist()


@st.cache_data(ttl=600)
def schedule(season: int, team: str) -> pd.DataFrame:
    return query("""
        select week, game_date, venue_role, opponent, opponent_conference,
               is_conference_game, result, points_for, points_against, margin,
               venue, attendance, season_type, kickoff_time_known
        from mart_team_schedule
        where season = :season and team = :team
        order by game_date, week
    """, {"season": season, "team": team})


@st.cache_data(ttl=600)
def season_record(season: int, team: str) -> pd.DataFrame:
    return query("""
        select season, school, conference, classification, games_played, wins, losses,
               ties, points_for, points_against, point_differential, win_pct,
               is_listed_team
        from mart_team_season_record
        where season = :season and school = :team
    """, {"season": season, "team": team})


@st.cache_data(ttl=600)
def team_history(team: str) -> pd.DataFrame:
    return query("""
        select season, conference, games_played, wins, losses, ties,
               points_for, points_against, point_differential, win_pct
        from mart_team_season_record
        where school = :team
        order by season desc
    """, {"team": team})


@st.cache_data(ttl=300)
def freshness() -> pd.DataFrame:
    return query("""
        select endpoint, last_success_at, hours_since_last_success, last_row_count,
               lost_its_data, never_succeeded
        from mart_data_freshness
        order by hours_since_last_success
    """)


@st.cache_data(ttl=300)
def data_as_of() -> Optional[pd.Timestamp]:
    """The freshest successful pull across the endpoints the site actually reads.

    Deliberately not `max()` over every endpoint: an hourly lines snapshot would make the
    stamp look fresher than the data on the page.
    """
    df = query("""
        select max(last_success_at) as as_of
        from mart_data_freshness
        where endpoint in ('games', 'teams', 'calendar')
    """)
    value = df["as_of"].iloc[0] if not df.empty else None
    return value if pd.notna(value) else None
