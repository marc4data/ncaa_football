"""Standings — page 5. Conference standings with the tiebreakers already resolved."""
import pandas as pd
import streamlit as st

from lib import filters, fmt, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    scope = filters.game_scope(show_week=False)
    season = scope.season
    table.dataset_caption("Standings", "srv_standings")

    with states.section("srv_standings"):
        df = query("""
            select season, team_id, school, team_slug, team_display, logo_url,
                   conference, division, classification, tiebreak_rank, tiebreak_basis,
                   wins, losses, ties, conference_wins, conference_losses,
                   win_pct, conference_win_pct,
                   points_for, points_against, point_differential,
                   home_record_display, away_record_display, neutral_games,
                   current_streak_display, current_streak_outcome, last_5_display,
                   ats_record_display, ats_as_favorite_display, ats_as_underdog_display,
                   color_on_light, as_of_ts
            from srv_standings
            where season = :season
              and classification = any(:classifications)
              and (:conference is null or conference = :conference)
            order by conference, tiebreak_rank
            limit 1000
        """, {"season": season, "classifications": scope.classifications,
              "conference": scope.conference})
        table.as_of_caption(df)

        states.render_or_state(
            df, "srv_standings",
            "Conference standings would appear here.",
            f"No completed games have been recorded for {season} yet. Standings fill in "
            f"from the first Saturday.",
            renderer=lambda d: _by_conference(d, scope))

        # AC-5.6: the rating columns are ABSENT rather than blank, and the page says which
        # object they wait on rather than showing an empty column that reads as no data.
        if not df.empty:
            st.divider()
            states.degraded(
                "sp_plus_rating / elo_rating on srv_standings",
                "The ratings themselves are built — see any team's Ratings tab — but they "
                "are not yet carried as columns here, so this table ranks on results "
                "alone.",
                scheduled="carrying fct_team_rating across to Standings")


COLUMNS = [
    # AC-5.1: tiebreak_rank is a COLUMN. The app never sorts by business logic —
    # conference tiebreakers are dbt's job and a Python sort implementing them is a
    # defect, not a shortcut.
    Col("tiebreak_rank", "#", "num", dp=0),
    Col("team", "Team", render=lambda r: table.team_cell(
        r, "team_slug", "team_display", "logo_url")),
    # AC-5.3: pre-formatted strings from the view. Nothing here assembles "5-7".
    Col("conf_record", "Conf", render=lambda r: _conference_record(r)),
    Col("conference_win_pct", "Conf %", "num"),
    Col("overall", "Overall", render=lambda r: _overall_record(r)),
    Col("home_record_display", "Home"),
    Col("away_record_display", "Away"),
    Col("current_streak_display", "Streak", render=lambda r: _streak(r)),
    Col("last_5_display", "Last 5"),
    Col("ats_record_display", "ATS"),
    Col("points_for", "PF", "num", dp=0),
    Col("points_against", "PA", "num", dp=0),
    Col("point_differential", "Diff", "signed", dp=0),
]


def _record(wins, losses) -> str:
    """A record, or an em dash where nothing has been played.

    Zero and absent are different claims, and this is the column the distinction was first
    got wrong on: every 2026 team showed 0-0-0 for a season that had not started.
    """
    if pd.isna(wins) or pd.isna(losses) or (int(wins) + int(losses) == 0):
        return fmt.EM_DASH
    return f"{int(wins)}-{int(losses)}"


def _overall_record(row) -> str:
    return _record(row.get("wins"), row.get("losses"))


def _conference_record(row) -> str:
    return _record(row.get("conference_wins"), row.get("conference_losses"))


def _streak(row) -> str:
    """W-streaks and L-streaks are the same shape and opposite news, so the glyph carries
    the direction rather than colour alone (AC-G.22)."""
    value = row.get("current_streak_display")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fmt.EM_DASH
    outcome = str(row.get("current_streak_outcome") or "")
    arrow = "▲" if outcome == "W" else ("▼" if outcome == "L" else "—")
    return f"{arrow} {value}"


def _by_conference(df: pd.DataFrame, scope) -> None:
    """AC-5.2: grouped by conference, and by division WHERE A CONFERENCE HAS THEM.

    Only 14 of 136 FBS teams had a division in 2025 — the SEC and Big Ten dropped theirs in
    2024 — so a division header is the exception now, not the rule. The absence must render
    as normal rather than as missing data: a Degraded state for the other 90% would be
    reporting a defect that does not exist.
    """
    for conference, rows in df.groupby("conference", sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{conference}</div>", unsafe_allow_html=True)
        divisions = [d for d in rows["division"].dropna().unique()]
        if divisions:
            for division in sorted(divisions):
                block = rows[rows["division"] == division]
                st.caption(division)
                _render(block, scope)
            # A conference can have divisions and still have teams outside them, which is
            # what a mid-season realignment looks like in the data.
            rest = rows[rows["division"].isna()]
            if not rest.empty:
                st.caption("No division recorded")
                _render(rest, scope)
        else:
            _render(rows, scope)

        basis = rows["tiebreak_basis"].dropna().unique()
        if len(basis):
            st.caption(f"Tiebreak: {basis[0]}. cfdb's own ordering, not an official "
                       f"standing — real conference tiebreakers involve head-to-head.")


def _render(rows: pd.DataFrame, scope) -> None:
    # AC-5.4: team click -> Team page, carrying the scope forward.
    table.render(rows, COLUMNS, caption="",
                 link_builder=lambda r: scope.link("team", team=r["team_slug"]))


def render() -> None:
    shell.render_page("standings", body)
