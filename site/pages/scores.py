"""Scores — page 3. Completed results with the model's call alongside the outcome."""
import pandas as pd
import streamlit as st

from lib import chips, filters, params, shell, states, table
from lib.query import query
from lib.table import Col


def _rows(season, week, season_type, conference) -> pd.DataFrame:
    return query("""
        select game_id, season, week, game_date, start_date_et,
               home_team_slug, home_team_display, home_logo_url, home_points, home_rank,
               away_team_slug, away_team_display, away_logo_url, away_points, away_rank,
               actual_margin, excitement_index, is_upset, attendance, venue_display,
               is_completed, as_of_ts
        from srv_scoreboard
        where season = :season and season_type = :season_type and is_completed
          and (:week is null or week = :week)
        order by game_date desc, start_date_et desc
        limit 400
    """, {"season": season, "week": week, "season_type": season_type})


def _winner(row) -> str:
    """AC-3.1: where actual_margin < 0 the HOME team won. The page must not undo the
    convention in display code — it held 3,402/3,402 in the data."""
    margin = row.get("actual_margin")
    if margin is None or pd.isna(margin):
        return chips.chip_html("w", "Pending")
    if margin == 0:
        return chips.chip_html("w", "Tie")
    winner = row["home_team_display"] if margin < 0 else row["away_team_display"]
    return f"<strong>{winner}</strong>"


def body(page) -> None:
    scope = filters.game_scope()
    with states.section("srv_scoreboard"):
        df = _rows(scope.season, scope.week, scope.season_type, scope.conference)
        table.as_of_caption(df)
        columns = [
            Col("away", "Away", render=lambda r: table.team_cell(
                r, "away_team_slug", "away_team_display", "away_logo_url", "away_rank")),
            Col("away_points", "", "num", dp=0),
            Col("home", "Home", render=lambda r: table.team_cell(
                r, "home_team_slug", "home_team_display", "home_logo_url", "home_rank")),
            Col("home_points", "", "num", dp=0),
            Col("winner", "Winner", render=_winner),
            # away minus home, stated so the sign is never guessed at.
            Col("actual_margin", "Margin (away−home)", "signed"),
            # AC-3.6: a column, never an app-side rank comparison.
            Col("is_upset", "Upset", render=lambda r: chips.chip_html("p", "Upset")
                if r.get("is_upset") else ""),
            Col("excitement_index", "Excitement", "num", dp=1),
            Col("attendance", "Attendance", "num", dp=0),
        ]
        states.render_or_state(
            df, "srv_scoreboard",
            "Completed results would be listed here.",
            f"No completed games for {scope.describe()} yet.",
            renderer=lambda d: _grouped(d, columns),
            fix_label="Clear filters", fix=filters.clear)


def _grouped(df, columns) -> None:
    """AC-3.5: grouped by day, most recent first."""
    for day, rows in df.groupby(df["game_date"], sort=False):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        table.render(rows, columns, caption="srv_scoreboard",
                     link_builder=lambda r: params.link("matchup", game_id=r["game_id"]))


def render() -> None:
    shell.render_page("scores", body)
