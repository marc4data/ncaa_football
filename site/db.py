"""Database access for the site.

Two rules this module exists to enforce:

1. **Read-only.** The site connects as `cfdb_read`, a role with SELECT and nothing else —
   verified at creation against INSERT/DELETE/CREATE/DROP. Serving is read-only by
   architecture, not by convention, so a bug in a page cannot write to the warehouse.
2. **Serving only.** Every query selects from exactly one `srv_*` table (G-1, AC-G.3). If a
   page needs a number that is not in a serving view, the answer is a new dbt model, not a
   calculation here — the standing boundary, which matters most under schedule pressure.

   Repointed off `mart_*` on 2026-08-20 once the parity gate was met: srv_standings against
   mart_team_season_record and srv_team_game_log against mart_team_schedule both pass, and
   the columns this module reads exist under the same names in both. That is what made the
   cutover a rename rather than a rewrite.

3. **Every list query carries an explicit LIMIT** (AC-G.39). srv_team_game_log is 221,268
   rows; an unbounded select is a defect even when the filter makes it small today.
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
    df = query("select distinct season from srv_team_game_log order by season desc limit 200")
    return df["season"].tolist()


@st.cache_data(ttl=600)
def teams_for_season(season: int) -> list:
    df = query("""
        select distinct team
        from srv_team_game_log
        where season = :season
        order by team
        limit 1000
    """, {"season": season})
    return df["team"].tolist()


@st.cache_data(ttl=600)
def schedule(season: int, team: str) -> pd.DataFrame:
    return query("""
        select week, game_date, venue_role, opponent, opponent_conference,
               is_conference_game, result, points_for, points_against, margin,
               venue, attendance, season_type, kickoff_time_known
        from srv_team_game_log
        where season = :season and team = :team
        order by game_date, week
        limit 500
    """, {"season": season, "team": team})


@st.cache_data(ttl=600)
def season_record(season: int, team: str) -> pd.DataFrame:
    return query("""
        select season, school, conference, classification, games_played, wins, losses,
               ties, points_for, points_against, point_differential, win_pct,
               is_listed_team
        from srv_standings
        where season = :season and school = :team
    """, {"season": season, "team": team})


@st.cache_data(ttl=600)
def team_history(team: str) -> pd.DataFrame:
    return query("""
        select season, conference, games_played, wins, losses, ties,
               points_for, points_against, point_differential, win_pct
        from srv_standings
        where school = :team
        order by season desc
        limit 200
    """, {"team": team})


@st.cache_data(ttl=300)
def freshness() -> pd.DataFrame:
    """RETIRED. Endpoint-level freshness is back-of-house content.

    The standalone banner read `mart_data_freshness`, the last `mart_*` dependency in the
    app. It is not replaced by a serving equivalent: AC-G.35 requires each page to carry an
    `as_of_ts` from its OWN view, which is both more accurate and per-domain, and AC-1.7
    says endpoint detail belongs on System Overview rather than front of house.

    Retiring an element is not a cutover, so no parity proof is owed for it.
    """
    raise NotImplementedError(
        "Freshness banner retired; use as_of_ts from the page's own serving view.")


@st.cache_data(ttl=300)
def data_as_of() -> Optional[pd.Timestamp]:
    """When the data behind THIS page was last loaded.

    Deliberately per-view rather than global: a 4-hourly lines snapshot would otherwise make
    every page look fresher than its own data. mart_as_of computes freshness per domain in
    dbt and each serving view carries its own.
    """
    # AC-G.35: the stamp comes from a COLUMN on the page's own serving view, never from
    # now() and no longer from an endpoint-level freshness mart. srv_team_game_log is what
    # this page reads, so its as_of_ts is the honest answer for this page — a different page
    # reading a different view will legitimately show a different one.
    df = query("""
        select max(as_of_ts) as as_of
        from srv_team_game_log
        limit 1
    """)
    value = df["as_of"].iloc[0] if not df.empty else None
    return value if pd.notna(value) else None
