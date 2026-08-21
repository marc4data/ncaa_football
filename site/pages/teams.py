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
                   color_on_dark, color_source_light, wins, losses, win_pct, as_of_ts
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

        states.render_or_state(
            df, "srv_teams_index",
            "Teams would be listed here.",
            f"No teams match “{search}”." if search else
            f"No teams for {scope.describe()}.",
            renderer=lambda d: _by_conference(d, scope))


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
