"""Schedule — page 2.

GRAIN IS ONE ROW PER GAME (AC-2.1). This is the inversion the spec once carried backwards:
a count on srv_schedule equals the game count for the filtered scope, never twice it,
because the view reads fct_game rather than fct_game_team.
"""
import pandas as pd
import streamlit as st

from lib import filters, shell, states, table
from lib.query import query
from lib.table import Col


def _rows(season: int, week, season_type: str, conference,
          division: str = 'fbs') -> pd.DataFrame:
    sql = """
        select game_id, season, week, season_type, start_date_et, game_date,
               home_team_slug, home_team_display, home_logo_url, home_conference,
               home_points, home_rank,
               away_team_slug, away_team_display, away_logo_url, away_conference,
               away_points, away_rank,
               venue_display, network, is_neutral_site, is_conference_game, is_completed,
               spread_current, total_current, predicted_margin, home_win_probability,
               excitement_index, as_of_ts
        from srv_schedule
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          -- FBS spine: EITHER team FBS, defaulted rather than hardcoded, so
          -- 'All divisions' in the filter bar genuinely widens it.
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        order by start_date_et, game_id
        limit 400
    """
    return query(sql, {"season": season, "week": week, "season_type": season_type,
                       "conf": conference, "division": division})


def _columns(scope) -> list:
    return [
        # AC-2.5: the row goes to the game, the team NAME goes to the team, and the two are
        # visually distinct. Both are real hrefs carrying the current scope forward, so a
        # season chosen here survives the click.
        Col("start_date_et", "Kickoff", "time"),
        Col("away", "Away", render=lambda r: table.team_cell(
            r, "away_team_slug", "away_team_display", "away_logo_url", "away_rank"),
            link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
        Col("away_points", "", "num", dp=0),
        Col("home", "Home", render=lambda r: table.team_cell(
            r, "home_team_slug", "home_team_display", "home_logo_url", "home_rank"),
            link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
        Col("home_points", "", "num", dp=0),
        Col("spread_current", "Spread", "signed"),
        Col("total_current", "Total", "num"),
        # Home-perspective is a derived, explicitly named column upstream; the raw
        # predicted_margin keeps the pack's away-minus-home sign (AC-1.4, AC-10.5).
        Col("predicted_margin", "Pred margin", "signed"),
        Col("network", "TV"),
        # F2-19: neutral site is a property a reader scans for; venue is detail and moved
        # to Matchup (F2-18), where there is room to name it properly.
        # The HEADER is a word and the CELL is a mark — the same rule the Upset column
        # needed. A column headed with a single character is a puzzle, which is exactly the
        # complaint that made "!" become "Upset" one page over.
        Col("is_neutral_site", "Neutral",
            render=lambda r: "◇" if r.get("is_neutral_site") else ""),
        table.details_col(lambda r: scope.link("matchup",
                                               game_id=r["game_id"])),
    ]


def body(page) -> None:
    scope = filters.game_scope()
    table.dataset_caption("Schedule", "srv_schedule")
    with states.section("srv_schedule"):
        df = _rows(scope.season, scope.week, scope.season_type, scope.conference,
                   scope.division)
        table.as_of_caption(df)
        states.render_or_state(
            df, "srv_schedule",
            "The week's games would be listed here.",
            f"No games match {scope.describe()}.",
            renderer=lambda d: _grouped(d, scope),
            fix_label="Clear filters", fix=filters.clear)


def _grouped(df: pd.DataFrame, scope) -> None:
    """AC-2.2: grouped by day, kickoff order within a day, with day headers."""
    # F2-06: one layout over the whole frame, reused by every group.
    layout = table.column_layout(df, _columns(scope))
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                    unsafe_allow_html=True)
        table.render(rows, _columns(scope), caption="", layout=layout,
                     link_builder=lambda r: scope.link("matchup",
                                                       game_id=r["game_id"]))


def render() -> None:
    shell.render_page("schedule", body)
