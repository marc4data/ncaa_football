"""Team page — page 8. One team, tabs, everything cfdb knows this season.

AC-8.2 is the criterion this page proves: a blocked TAB does not block the PAGE. Overview
and Schedule render fully; Ratings, Roster and Trends name what they wait on. The pattern
was written for Roster and now earns its keep three times.
"""
import streamlit as st

from lib import identity, params, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    seasons = query("select distinct season from srv_team_overview order by season desc limit 200")
    options = seasons["season"].tolist()
    season = params.get("season") or (options[0] if options else None)
    teams = query("""select team_slug, team_display from srv_team_overview
                     where season = :season order by team_display limit 1200""",
                  {"season": season})
    if teams.empty:
        states.empty("A team profile would be here.", f"No teams for season {season}.")
        return

    slugs = teams["team_slug"].tolist()
    current = params.get("team")
    # The URL may carry a display name from an older link; resolve it rather than 404.
    if current not in slugs:
        match = teams[teams["team_display"].str.lower() == str(current).lower()]
        current = match["team_slug"].iloc[0] if not match.empty else slugs[0]

    with st.sidebar:
        season = st.selectbox("Season", options,
                              index=options.index(season) if season in options else 0)
        label = st.selectbox("Team", teams["team_display"].tolist(),
                             index=slugs.index(current) if current in slugs else 0)
    current = teams[teams["team_display"] == label]["team_slug"].iloc[0]
    params.set_params(season=season, team=current)

    overview = query("""
        select season, team_slug, team_display, mascot, conference, division,
               classification, logo_url, color_on_light, color_on_dark, color_source,
               wins, losses, record_display, conference_record_display, conference_standing,
               ats_record_display, ats_as_favorite_display, ats_as_underdog_display, as_of_ts
        from srv_team_overview
        where season = :season and team_slug = :team
        limit 1
    """, {"season": season, "team": current})

    if overview.empty:
        states.empty("This team's profile would be here.",
                     f"No record for {label} in {season}.")
        return

    row = overview.iloc[0]
    _identity_header(row)
    table.as_of_caption(overview)

    tabs = st.tabs(["Overview", "Schedule", "Ratings", "Roster", "Trends"])
    with tabs[0]:
        _overview(row)
    with tabs[1]:
        _game_log(season, row.get('team_display'))
    with tabs[2]:
        # AC-8.2: this tab is Degraded while the page around it works.
        states.degraded("fct_team_week_rating",
                        "SP+, Elo, SRS and the profile percentiles are not built yet.",
                        scheduled="Track B1 — the largest enrichment in the backlog")
    with tabs[3]:
        states.degraded("dim_athlete",
                        "Rosters need the athlete dimension and the player facts.",
                        scheduled="Track B8 — after the other blocked pages")
    with tabs[4]:
        states.degraded("fct_team_week_rating",
                        "Week-over-week trends need a rating per team per week.",
                        scheduled="Track B1")


def _identity_header(row) -> None:
    """AC-8.6: the colour band uses the contrast-safe text colour from dim_team.
    The app computes no contrast — it reads what dbt already solved."""
    logo = identity.logo_or_monogram(row.get("logo_url"), row.get("team_display"), 44)
    text_colour = identity.text_on(row)
    st.markdown(
        f"<div style='{identity.accent_style(row)};display:flex;align-items:center;"
        f"gap:.7rem;margin:.3rem 0 1rem'>{logo}"
        f"<div><div style='font-size:1.35rem;font-weight:600;color:{text_colour}'>"
        f"{row.get('team_display')}</div>"
        f"<div style='opacity:.7;font-size:.88rem'>{row.get('mascot') or ''} · "
        f"{row.get('conference') or 'Independent'}</div></div></div>",
        unsafe_allow_html=True)


def _overview(row) -> None:
    cols = st.columns(4)
    # AC-5.3 / AC-G.2: records are pre-formatted strings from the view, never assembled here.
    cols[0].metric("Record", row.get("record_display") or "—")
    cols[1].metric("Conference", row.get("conference_record_display") or "—")
    cols[2].metric("Conf. standing", int(row["conference_standing"])
                   if row.get("conference_standing") == row.get("conference_standing")
                   and row.get("conference_standing") is not None else "—")
    cols[3].metric("ATS", row.get("ats_record_display") or "—")
    st.caption(f"ATS as favourite {row.get('ats_as_favorite_display') or '—'} · "
               f"as underdog {row.get('ats_as_underdog_display') or '—'}")


def _game_log(season, team_display) -> None:
    with states.section("srv_team_game_log"):
        df = query("""
            select week, game_id, game_date, opponent, opponent_conference, venue_role,
                   is_neutral_site, result, points_for, points_against, margin,
                   is_completed, as_of_ts
            from srv_team_game_log
            where season = :season and team = :team_display
            order by game_date, week
            limit 60
        """, {"season": season, "team_display": team_display})
        states.render_or_state(
            df, "srv_team_game_log",
            "This team's games would be listed here.",
            "No games recorded for this team-season.",
            renderer=lambda d: table.render(d, [
                Col("week", "Wk", "num", dp=0),
                Col("game_date", "Date", "datetime"),
                Col("venue_role", "H/A"),
                Col("opponent", "Opponent"),
                Col("result", "Result"),
                Col("points_for", "PF", "num", dp=0),
                Col("points_against", "PA", "num", dp=0),
                # AC-8.3: oriented to the SUBJECT team, not to home.
                Col("margin", "Margin (team)", "signed", dp=0),
            ], caption="srv_team_game_log",
                link_builder=lambda r: params.link("matchup", game_id=r["game_id"])))


def render() -> None:
    shell.render_page("team", body)
