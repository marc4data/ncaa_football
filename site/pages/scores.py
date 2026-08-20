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
               winner, actual_margin, excitement_index, is_upset, attendance, venue_display,
               is_completed, as_of_ts
        from srv_scoreboard
        where season = :season and season_type = :season_type and is_completed
          and (:week is null or week = :week)
        order by game_date desc, start_date_et desc
        limit 400
    """, {"season": season, "week": week, "season_type": season_type})


def _winner(row) -> str:
    """AC-3.1. The winner is READ, not derived.

    This used to pick the winner by the sign of actual_margin and index into the display
    columns. Two problems, both found by rehearsing the post-game path against real 2025
    games rather than 2026 fixtures where every score is null:

      1. It is the app owning a definition dbt already owns. srv_scoreboard computes
         `winner` from the points, and a second derivation is a second answer waiting to
         disagree — which it did, on one game in 295.
      2. It indexed into a column that can be NULL and rendered `<strong>None</strong>`.
         The display name is fixed at the view now, but a formatter that assumes a value is
         present is the thing that broke, and reading the view's own answer removes the
         assumption rather than guarding it.

    The sign convention is still asserted — in dbt, against the data, where it belongs.
    """
    if not row.get("is_completed"):
        return chips.chip_html("w", "Pending", "this game has not been played")
    winner = row.get("winner")
    if winner is None or (isinstance(winner, float) and pd.isna(winner)):
        # The view returns NULL for a completed game with equal scores. A tie is a settled
        # result and must not render as Pending.
        return chips.chip_html("w", "Tie", "a settled result, not an unplayed game")
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
