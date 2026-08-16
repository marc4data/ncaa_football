"""cfdb — college football data site.

Reads marts from serving Postgres and displays them. It computes nothing: every number on
every page comes from a dbt model. Sorting, filtering and formatting are presentation;
a new number is a new mart, requested through the demand-driven process.

Run locally:
    streamlit run site/app.py
"""
import streamlit as st

import db

st.set_page_config(page_title="cfdb — college football data", page_icon="🏈",
                   layout="wide")


def freshness_banner():
    """Data quality rule #5: every page shows how old its data is."""
    as_of = db.data_as_of()
    if as_of is None:
        st.warning("No successful data pull recorded — the pipeline may not have run.")
        return
    st.caption(f"Data as of {as_of:%Y-%m-%d %H:%M} UTC · source: CollegeFootballData.com")


def record_line(record):
    """Format a W-L(-T) record. Formatting, not calculation — the counts come from dbt."""
    if record.empty:
        return None
    row = record.iloc[0]
    base = f"{int(row.wins)}–{int(row.losses)}"
    return f"{base}–{int(row.ties)}" if row.ties else base


st.title("🏈 College Football Data")

seasons = db.seasons()
if not seasons:
    st.error("No seasons available. Has the pipeline run?")
    st.stop()

left, right = st.columns([1, 3])
with left:
    season = st.selectbox("Season", seasons, index=0)
    team_list = db.teams_for_season(season)
    default_team = team_list.index("Oklahoma State") if "Oklahoma State" in team_list else 0
    team = st.selectbox("Team", team_list, index=default_team)

with right:
    record = db.season_record(season, team)
    schedule = db.schedule(season, team)

    if record.empty:
        # Scheduled but unplayed seasons have no record yet — that is the correct state
        # for 2026 today, not an error.
        played = schedule["result"].notna().sum() if not schedule.empty else 0
        st.subheader(f"{team} — {season}")
        st.info(f"No completed games yet: {len(schedule)} scheduled, {played} played.")
    else:
        row = record.iloc[0]
        st.subheader(f"{team} — {season}")
        cols = st.columns(5)
        cols[0].metric("Record", record_line(record))
        cols[1].metric("Conference", row.conference or "—")
        cols[2].metric("Points for", int(row.points_for))
        cols[3].metric("Points against", int(row.points_against))
        cols[4].metric("Differential", int(row.point_differential))
        if not row.is_listed_team:
            st.caption("Not in CFBD's team list for this season — schedule data only.")

st.markdown("### Schedule")
if schedule.empty:
    st.info("No games found for this team and season.")
else:
    display = schedule.copy()
    display["Date"] = display["game_date"].astype(str)
    # Seasons before 2001 have no recorded kickoff time; say so rather than implying one.
    display.loc[~display["kickoff_time_known"], "Date"] += " (date only)"
    display["Site"] = display["venue_role"].str.title()
    display["Score"] = display.apply(
        lambda r: "—" if r.points_for is None or r.result is None
        else f"{r.result} {int(r.points_for)}–{int(r.points_against)}", axis=1)
    display["Conf"] = display["is_conference_game"].map({True: "✓", False: ""})

    st.dataframe(
        display[["week", "Date", "Site", "opponent", "opponent_conference", "Conf",
                 "Score", "venue"]].rename(columns={
                     "week": "Wk", "opponent": "Opponent",
                     "opponent_conference": "Opp. Conference", "venue": "Venue"}),
        hide_index=True, use_container_width=True)

with st.expander(f"{team} — season by season"):
    history = db.team_history(team)
    if history.empty:
        st.info("No completed seasons recorded.")
    else:
        st.dataframe(history, hide_index=True, use_container_width=True)

freshness_banner()
