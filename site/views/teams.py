"""Teams — page 7. The index: find a team, see its shape, click through."""
import pandas as pd
import streamlit as st

from lib import filters, fmt, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    # Week does not apply to a team index; conference is offered as a filter here rather
    # than only as a grouping, which is what was missing.
    scope = filters.game_scope(show_week=False)
    table.dataset_caption("Teams", "srv_teams_index")
    search = st.text_input("Search teams", placeholder="Type to filter…")

    with states.section("srv_teams_index"):
        df = query("""
            select season, team_id, school, team_slug, team_display, abbreviation,
                   conference, classification, logo_source_url, color_on_light,
                   color_on_dark, color_source_light, wins, losses, win_pct,
                   yards_for, rushing_yards_for, passing_yards_for,
                   yards_allowed, rushing_yards_allowed, passing_yards_allowed,
                   games_with_box_score, as_of_ts
            from srv_teams_index
            where season = :season
              and classification = any(:classifications)
              and (:conference is null or conference = :conference)
            order by conference, school
            limit 1200
        """, {"season": scope.season, "classifications": scope.classifications,
              "conference": scope.conference})
        table.as_of_caption(df)

        if search:
            df = df[df["school"].str.contains(search, case=False, na=False)]

        df = table.apply_sort(df, [Col("abbreviation", "Abbr"),
                                   Col("win_pct", "Win %", "num")])
        states.render_or_state(
            df, "srv_teams_index",
            "Teams would be listed here.",
            f"No teams match “{search}”." if search else
            f"No teams for {scope.describe()}.",
            renderer=lambda d: _by_conference(d, scope))

        # AC-G.33: the yardage columns are not season-complete, and the page says so once
        # rather than repeating a caveat per row.
        if not df.empty:
            covered = int(df["games_with_box_score"].fillna(0).gt(0).sum())
            st.caption(
                f"Yardage is from box scores, which CFBD publishes from 2024 onward — "
                f"{covered:,} of {len(df):,} teams shown have any. Blank means no box "
                f"score, not zero yards.")


def _team(row) -> str:
    """The team, with ONE affordance: the name is the link.

    The colour-source hint used to render a small circle here whose tooltip explained
    itself only on hover. Two problems, and the first one made the second worse: its guard
    checked for a rung value dim_team never emits, so it fired on every one of 34,061 rows
    including the 29,903 that use the team's own primary colour. A marker on everything
    marks nothing, and an unexplained glyph next to a team name reads as a control.

    Colour-source debt is a BUILDER's concern and stays on the data-quality surfaces, the
    same split that put friendly dataset names on front-of-house pages and left the literal
    object name on System Overview.
    """
    return table.team_cell(row, "team_slug", "team_display", "logo_source_url")


def _record(row) -> str:
    """Null, not 0-0, before a season starts. Same rule as Standings."""
    wins, losses = row.get("wins"), row.get("losses")
    if pd.isna(wins) or pd.isna(losses) or int(wins) + int(losses) == 0:
        return fmt.EM_DASH
    return f"{int(wins)}-{int(losses)}"


def _by_conference(df, scope) -> None:
    """AC-7.1: grouped by conference, alphabetical within."""
    columns = [
        Col("team", "Team", render=_team,
            link=lambda r: scope.link("team", team=r["team_slug"])),
        Col("abbreviation", "Abbr"),
        Col("record", "Record", render=_record),
        Col("win_pct", "Win %", "num"),
        # R-003. Six numeric columns on ~136 FBS rows. AC-G.40's budget is stated WITH its
        # filter rather than as a bare number: this is fine at the FBS default and is the
        # reason the division filter defaults where it does — an all-divisions render is
        # 681 rows, and six more columns there is a different question.
        Col("yards_for", "Yds", "num", dp=0),
        Col("rushing_yards_for", "Rush", "num", dp=0),
        Col("passing_yards_for", "Pass", "num", dp=0),
        Col("yards_allowed", "Yds all", "num", dp=0),
        Col("rushing_yards_allowed", "Rush all", "num", dp=0),
        Col("passing_yards_allowed", "Pass all", "num", dp=0),
    ]
    # F2-06/F2-27: computed over every conference at once, so the grid does not reflow
    # per group.
    layout = table.column_layout(df, columns)
    for conference, rows in df.groupby("conference", sort=True, dropna=False):
        st.markdown(f"<div class='cfdb-daygroup'>{conference or 'Independent'}</div>",
                    unsafe_allow_html=True)
        # Mascot removed: it never distinguished two teams or answered a question.
        # AC-7.5: the row goes to the team page, carrying the scope forward.
        table.render(rows, columns, caption="", layout=layout,
                     link_builder=lambda r: scope.link("team", team=r["team_slug"]))


def render() -> None:
    shell.render_page("teams", body)
