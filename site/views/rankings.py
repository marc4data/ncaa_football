"""Rankings — page 4. Poll standings, movement, and where the polls disagree."""
import streamlit as st

from lib import filters, params, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    # F2-03: the bar renders on every data page, so a scope inherited from
    # another page is visible on arrival rather than silently in effect.
    # F2-01 was reported still broken on this route, and the reason was that this page
    # never called the shared bar at all — it had its own season and week selectboxes, so
    # an inbound scope was neither read nor written and every arrival reset to the default.
    scope = filters.game_scope(
        conference_note="Polls rank teams nationally, so a conference does not scope them.",
        show_conference=False)
    table.dataset_caption("Rankings", "srv_rankings")
    season = scope.season

    weeks = query("""select distinct week from srv_rankings
                     where season = :season order by week desc limit 40""",
                  {"season": season})["week"].tolist()
    # The global week is honoured where the polls published one; otherwise the most recent
    # poll week, because a rankings page with no week is a rankings page with no content.
    week = scope.week if scope.week in weeks else (weeks[0] if weeks else None)

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
                # 🚨 A169 (cfdb-main-R-1320). THE NAME READS AS A LINK — Marc, Site v07.
                # It was already clickable via the row's `link_builder`, but that wraps every
                # cell in `cfdb-cell-link`, which is `color:inherit; text-decoration:none`:
                # **the destination was right and the affordance was missing.** `Col.link`
                # wins over the row link for this cell, so nothing nests.
                Col("team", "Team", render=lambda r: table.team_cell(
                    r, "team_slug", "team_display", "logo_url"),
                    link=table.team_link("team_slug")),
                Col("conference", "Conf"),
                Col("first_place_votes", "1st", "num", dp=0),
                Col("points", "Points", "num", dp=0),
            ], caption="srv_rankings",
                # ⚠️ A169: `team_slug`, NOT `team_display`. This was the only one of the three
                # pages routing by DISPLAY NAME — `/team?team=Ohio State` against standings'
                # `team=miami` — and it worked only because `team.py` carries a reverse lookup
                # for *"a display name from an older link"*. **Relying on a compatibility
                # branch is not the same as being right**, and the slug is already selected
                # two lines up.
                link_builder=lambda r: params.link("team", team=r["team_slug"],
                                                   season=season)))


def _compare(season, week) -> None:
    """AC-4.4: fed by the PRE-PIVOTED view. No pivot happens in Streamlit."""
    with states.section("srv_rankings_compare"):
        # A170: `team_slug` and `season` are selected for the link — team_link reads the
        # season off the row to carry it through to the team page, and a slug that is not
        # selected cannot be linked. `season` is already in the WHERE; selecting it costs
        # nothing and makes the row self-describing.
        df = query("""
            select school, team_slug, season, conference_name, ap_rank, coaches_rank,
                   committee_rank, disagreement_spread, as_of_ts
            from srv_rankings_compare
            where season = :season and week = :week
            order by disagreement_spread desc nulls last, ap_rank
            limit 200
        """, {"season": season, "week": week})
        table.as_of_caption(df)
        # AC-4.5 said this was "sortable here" and it was not — the headers were static
        # text. F2-22. Sorting now happens through the URL like every other choice, so a
        # reader can send somebody "the week the polls disagreed most about Texas".
        compare_columns = [
                # A170 (cfdb-main-R-1322). The one team name on this page that could not be a
                # link until this round, because the view published no slug. `Col.link` rather
                # than a row link_builder, for A169's reason: it wins over the row link for
                # that cell, so nothing nests, and it is the form the anchor guard reads as safe.
                Col("school", "Team", link=table.team_link("team_slug")),
                Col("conference_name", "Conf"),
                Col("ap_rank", "AP", "num", dp=0),
                Col("coaches_rank", "Coaches", "num", dp=0),
                Col("committee_rank", "CFP", "num", dp=0),
                # AC-4.5: computed in dbt, sortable here, so "where do the polls disagree
                # most" is one click rather than an app-side calculation.
                Col("disagreement_spread", "Spread", "num", dp=0),
        ]
        # A141: `table.render` applies the sort it draws — see its docstring.
        states.render_or_state(
            df, "srv_rankings_compare",
            "Poll disagreement would be here.",
            f"No comparable polls for week {week}.",
            renderer=lambda d: table.render(d, compare_columns, caption=""))


def render() -> None:
    shell.render_page("rankings", body)
