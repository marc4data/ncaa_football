"""Teams — page 7. The index: find a team, see its shape, click through."""
import streamlit as st

from lib import identity, params, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    seasons = query("select distinct season from srv_teams_index order by season desc limit 200")
    options = seasons["season"].tolist()
    default = params.get("season") or (options[0] if options else None)
    with st.sidebar:
        season = st.selectbox("Season", options,
                              index=options.index(default) if default in options else 0)
        division = st.selectbox("Division", ["fbs", "fcs", "all"],
                                index=["fbs", "fcs", "all"].index(params.get("division") or "fbs"))
    params.set_params(season=season, division=division)
    search = st.text_input("Search teams", placeholder="Type to filter…")

    with states.section("srv_teams_index"):
        df = query("""
            select season, team_id, school, mascot, abbreviation, conference,
                   classification, logo_source_url, color_on_light, color_on_dark,
                   color_source_light, wins, losses, win_pct, as_of_ts
            from srv_teams_index
            where season = :season
              and (:division = 'all' or classification = :division)
            order by conference, school
            limit 1200
        """, {"season": season, "division": division})
        table.as_of_caption(df)

        if search:
            df = df[df["school"].str.contains(search, case=False, na=False)]

        states.render_or_state(
            df, "srv_teams_index",
            "Teams would be listed here.",
            f"No teams match “{search}”." if search else f"No teams for season {season}.",
            renderer=_by_conference)


def _team(row) -> str:
    """AC-7.2: a defaulted colour is identifiable, or it becomes invisible data debt."""
    cell = table.team_cell(row, "school", "school", "logo_source_url")
    return cell + identity.color_source_hint(
        {"color_source": row.get("color_source_light")})


def _by_conference(df) -> None:
    """AC-7.1: grouped by conference, alphabetical within."""
    for conference, rows in df.groupby("conference", sort=True, dropna=False):
        st.markdown(f"<div class='cfdb-daygroup'>{conference or 'Independent'}</div>",
                    unsafe_allow_html=True)
        table.render(rows, [
            Col("team", "Team", render=_team),
            Col("mascot", "Mascot"),
            Col("abbreviation", "Abbr"),
            Col("record", "Record",
                render=lambda r: f"{int(r['wins'] or 0)}-{int(r['losses'] or 0)}"),
            Col("win_pct", "Win %", "num"),
        ], caption="srv_teams_index",
            link_builder=lambda r: params.link("team", team=r["school"], season=r["season"]))


def render() -> None:
    shell.render_page("teams", body)
