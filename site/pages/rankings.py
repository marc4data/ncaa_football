"""Rankings — page 4. Poll standings, movement, and where the polls disagree."""
import streamlit as st

from lib import params, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    seasons = query("select distinct season from srv_rankings order by season desc limit 200")
    options = seasons["season"].tolist()
    default = params.get("season") or (options[0] if options else None)
    with st.sidebar:
        season = st.selectbox("Season", options,
                              index=options.index(default) if default in options else 0)
        weeks = query("""select distinct week from srv_rankings
                         where season = :season order by week desc limit 40""",
                      {"season": season})["week"].tolist()
        week = st.selectbox("Week", weeks, index=0) if weeks else None
    params.set_params(season=season, week=week)

    polls = query("""select distinct poll_name, poll_display_order from srv_rankings
                     where season = :season order by poll_display_order, poll_name limit 20""",
                  {"season": season})["poll_name"].tolist()
    if not polls:
        states.empty("Poll rankings would be here.", f"No polls published for {season}.")
        return

    # AC-4.2: one tab per poll, plus Compare. Tab selection lives in the URL.
    tabs = st.tabs(polls + ["Compare"])
    for tab, poll in zip(tabs[:-1], polls):
        with tab:
            _poll_table(season, week, poll)
    with tabs[-1]:
        _compare(season, week)


def _poll_table(season, week, poll) -> None:
    with states.section("srv_rankings"):
        df = query("""
            select rank, team_slug, team_display, logo_url, conference,
                   first_place_votes, points, is_receiving_votes, as_of_ts
            from srv_rankings
            where season = :season and week = :week and poll_name = :poll
            order by case when rank is null then 1 else 0 end, rank, points desc
            limit 200
        """, {"season": season, "week": week, "poll": poll})
        table.as_of_caption(df)
        states.render_or_state(
            df, "srv_rankings",
            f"The {poll} would be here.",
            f"No {poll} published for week {week}.",
            renderer=lambda d: table.render(d, [
                # AC-4.6: a team receiving votes but unranked is representable and visually
                # distinct from a team receiving none — it keeps a row, with no rank.
                Col("rank", "#", render=lambda r: (
                    f"{int(r['rank'])}" if r.get("rank") == r.get("rank")
                    and r.get("rank") is not None else "RV")),
                Col("team", "Team", render=lambda r: table.team_cell(
                    r, "team_slug", "team_display", "logo_url")),
                Col("conference", "Conf"),
                Col("first_place_votes", "1st", "num", dp=0),
                Col("points", "Points", "num", dp=0),
            ], caption="srv_rankings",
                link_builder=lambda r: params.link("team", team=r["team_display"],
                                                   season=season)))


def _compare(season, week) -> None:
    """AC-4.4: fed by the PRE-PIVOTED view. No pivot happens in Streamlit."""
    with states.section("srv_rankings_compare"):
        df = query("""
            select school, conference_name, ap_rank, coaches_rank, committee_rank,
                   disagreement_spread, as_of_ts
            from srv_rankings_compare
            where season = :season and week = :week
            order by disagreement_spread desc nulls last, ap_rank
            limit 200
        """, {"season": season, "week": week})
        table.as_of_caption(df)
        states.render_or_state(
            df, "srv_rankings_compare",
            "Poll disagreement would be here.",
            f"No comparable polls for week {week}.",
            renderer=lambda d: table.render(d, [
                Col("school", "Team"),
                Col("conference_name", "Conf"),
                Col("ap_rank", "AP", "num", dp=0),
                Col("coaches_rank", "Coaches", "num", dp=0),
                Col("committee_rank", "CFP", "num", dp=0),
                # AC-4.5: computed in dbt, sortable here, so "where do the polls disagree
                # most" is one click rather than an app-side calculation.
                Col("disagreement_spread", "Spread", "num", dp=0),
            ], caption="srv_rankings_compare"))


def render() -> None:
    shell.render_page("rankings", body)
