"""Standings — page 5. Conference standings with the tiebreakers already resolved."""
import streamlit as st

from lib import params, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    seasons = query("select distinct season from srv_standings order by season desc limit 200")
    default = params.get("season") or int(seasons["season"].iloc[0])
    with st.sidebar:
        season = st.selectbox("Season", seasons["season"].tolist(),
                              index=int(seasons["season"].tolist().index(default))
                              if default in seasons["season"].tolist() else 0)
    params.set_params(season=season)

    with states.section("srv_standings"):
        df = query("""
            select season, team_id, school, conference, classification, tiebreak_rank,
                   tiebreak_basis, wins, losses, ties, conference_wins, conference_losses,
                   win_pct, points_for, points_against, point_differential,
                   logo_source_url, color_on_light, as_of_ts
            from srv_standings
            where season = :season and classification in ('fbs','fcs')
            order by conference, tiebreak_rank
            limit 1000
        """, {"season": season})
        table.as_of_caption(df)

        columns = [
            # AC-5.1: tiebreak_rank is a COLUMN. The app never sorts by business logic —
            # conference tiebreakers are dbt's job and a Python sort implementing them is
            # a defect, not a shortcut.
            Col("tiebreak_rank", "#", "num", dp=0),
            Col("team", "Team", render=lambda r: table.team_cell(
                r, "school", "school", "logo_source_url")),
            Col("conf_record", "Conf",
                render=lambda r: f"{int(r['conference_wins'] or 0)}-{int(r['conference_losses'] or 0)}"),
            Col("overall", "Overall",
                render=lambda r: f"{int(r['wins'] or 0)}-{int(r['losses'] or 0)}"),
            Col("win_pct", "Win %", "num"),
            Col("points_for", "PF", "num", dp=0),
            Col("points_against", "PA", "num", dp=0),
            Col("point_differential", "Diff", "signed", dp=0),
        ]
        states.render_or_state(
            df, "srv_standings",
            "Conference standings would appear here.",
            f"No standings for season {season}.",
            renderer=lambda d: _by_conference(d, columns))


def _by_conference(df, columns) -> None:
    """AC-5.2: grouped by conference."""
    for conference, rows in df.groupby("conference", sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{conference}</div>", unsafe_allow_html=True)
        table.render(rows, columns, caption="srv_standings",
                     link_builder=lambda r: params.link("team", team=r["school"], season=r["season"]))
        basis = rows["tiebreak_basis"].dropna().unique()
        if len(basis):
            st.caption(f"Tiebreak: {basis[0]}")


def render() -> None:
    shell.render_page("standings", body)
