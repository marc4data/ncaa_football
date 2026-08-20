"""Matchup — page 10. One game, everything cfdb knows about it.

Four sections, and the interesting design problem is that they fail independently. A 2026
game has a market but no model row; a 1912 game has neither; a completed 2025 game has
both plus a result. Rendering "no data" once for the whole page would be wrong in every one
of those cases, so each section states its own absence and the page around it keeps working
— the same rule the Team page proves with tabs.

The model section is where the honesty rules land. `training_week_floor` is a COLUMN, not a
constant in this file: the floor is the model's property and it travels with the data, so
the copy cannot drift from what the model actually did.
"""
import pandas as pd
import streamlit as st

from lib import attribution, chips, fmt, identity, params, shell, states, table
from lib.query import query
from lib.table import Col

COLUMNS = """
    game_id, season, season_type, week, start_date_et, venue_display, attendance,
    is_completed, is_conference_game, is_neutral_site,
    home_team, home_abbreviation, home_conference, home_logo_url, home_color_on_light,
    home_color_on_dark, home_points, home_wins, home_losses,
    away_team, away_abbreviation, away_conference, away_logo_url, away_color_on_light,
    away_color_on_dark, away_points, away_wins, away_losses,
    spread, spread_open, over_under, over_under_open, home_moneyline, away_moneyline,
    provider_key, line_snapshot_ts, market_implied_home_win_probability,
    market_implied_away_win_probability, overround, devig_method,
    model_name, model_family, predicted_margin, predicted_margin_home_perspective,
    predicted_total_points, predicted_home_points, predicted_away_points,
    home_win_probability, confidence_bucket, home_cover_edge, home_win_probability_edge,
    is_out_of_sample_week, training_week_floor,
    actual_margin, actual_margin_home_perspective,
    series_games, series_home_team_wins, series_away_team_wins, series_ties,
    series_first_season, series_last_season,
    model_version_key, attribution, as_of_ts
"""


def body(page) -> None:
    with states.section("srv_matchup"):
        game_id = params.get("game_id")
        if game_id is None:
            _picker()
            return

        df = query(f"""
            select {COLUMNS}
            from srv_matchup
            where game_id = :game_id
            limit 1
        """, {"game_id": game_id})

        if df.empty:
            # A game_id that resolves to nothing is the user asking for something that does
            # not exist — Empty with the bad value named, never a blank page (AC-G.11).
            states.empty("This game would be here.",
                         f"No game with id {game_id} is in the schedule.")
            _picker()
            return

        row = df.iloc[0]
        params.set_params(game_id=game_id, season=int(row["season"]))
        _scoreline(row)
        table.as_of_caption(df)

        _market(row)
        _model(row)
        _series(row)


def _picker() -> None:
    """No game chosen. Offer the current week rather than an empty page."""
    seasons = query("select distinct season from srv_matchup order by season desc limit 200")
    if seasons.empty:
        states.empty("A game would be here.", "No games have been built yet.")
        return
    season = params.get("season") or int(seasons["season"].iloc[0])
    with st.sidebar:
        options = seasons["season"].tolist()
        season = st.selectbox("Season", options,
                              index=options.index(season) if season in options else 0)
    games = query("""
        select game_id, week, start_date_et, home_team, away_team, is_completed
        from srv_matchup
        where season = :season
        order by start_date_et desc, game_id
        limit 300
    """, {"season": season})
    states.render_or_state(
        games, "srv_matchup",
        "Pick a game to see the matchup.",
        f"No games recorded for {season}.",
        renderer=lambda d: table.render(d, [
            Col("start_date_et", "Kickoff", "datetime"),
            Col("week", "Wk", "num", dp=0),
            Col("away_team", "Away"),
            Col("home_team", "Home"),
        ], caption="srv_matchup",
            link_builder=lambda r: params.link("matchup", game_id=r["game_id"])))


def _scoreline(row) -> None:
    """Both teams, their colours, and the score if there is one.

    A scheduled game shows no score rather than 0–0. Two zeroes is a real result — a
    scoreless tie — and rendering an unplayed game the same way asserts something false.
    """
    played = bool(row.get("is_completed"))
    left, middle, right = st.columns([5, 2, 5])
    for column, side in ((left, "away"), (right, "home")):
        with column:
            logo = identity.logo_or_monogram(row.get(f"{side}_logo_url"),
                                             row.get(f"{side}_team") or "?", 40)
            record = f"{row.get(f'{side}_wins')}–{row.get(f'{side}_losses')}" \
                if pd.notna(row.get(f"{side}_wins")) else ""
            points = row.get(f"{side}_points")
            score = (f"<div style='font-size:2rem;font-weight:600'>{int(points)}</div>"
                     if played and pd.notna(points) else "")
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:.6rem'>{logo}"
                f"<div><div style='font-weight:600'>{row.get(f'{side}_team')}</div>"
                f"<div style='opacity:.7;font-size:.85rem'>"
                f"{row.get(f'{side}_conference') or 'Independent'}"
                f"{' · ' + record if record else ''}</div></div>{score}</div>",
                unsafe_allow_html=True)
    with middle:
        st.markdown(
            f"<div style='text-align:center;opacity:.75;font-size:.85rem'>"
            f"{'Final' if played else 'Scheduled'}<br>{fmt.eastern(row.get('start_date_et'))}"
            f"<br>{row.get('venue_display') or ''}"
            f"{'<br>neutral site' if row.get('is_neutral_site') else ''}</div>",
            unsafe_allow_html=True)


def _market(row) -> None:
    st.subheader("Market")
    if pd.isna(row.get("spread")) and pd.isna(row.get("over_under")):
        # Most of 110,634 games predate betting data entirely, which is an absence of
        # market rather than a failure to fetch one, so it renders Empty.
        states.empty("The betting market would be here.",
                     "No sportsbook line has been recorded for this game. "
                     "cfdb holds lines from 2013 onward, and only for games books priced.")
        return
    cols = st.columns(4)
    # AC-1.4 again: a home favourite is a NEGATIVE spread. Stated on the page, because this
    # is the number a reader is most likely to invert.
    cols[0].metric("Spread (home)", fmt.signed(row.get("spread"), "spread"),
                   help="Negative means the home team is favoured.")
    cols[1].metric("Total", fmt.number(row.get("over_under"), "over_under"))
    cols[2].metric("Home moneyline", fmt.signed(row.get("home_moneyline"), "", dp=0))
    cols[3].metric("Away moneyline", fmt.signed(row.get("away_moneyline"), "", dp=0))

    implied = row.get("market_implied_home_win_probability")
    if pd.notna(implied):
        st.caption(
            f"Implied home win probability {float(implied) * 100:.1f}% "
            f"(away {float(row.get('market_implied_away_win_probability')) * 100:.1f}%), "
            f"de-vigged by {row.get('devig_method')}; the book's overround was "
            f"{fmt.number(row.get('overround'), '', 4)}. Raw prices above are untouched.")
    st.caption(f"Line from {row.get('provider_key') or 'an unnamed book'}, "
               f"snapshot {fmt.eastern(row.get('line_snapshot_ts'))}. "
               f"Opening spread {fmt.signed(row.get('spread_open'), 'spread')}, "
               f"opening total {fmt.number(row.get('over_under_open'), 'over_under')}.")


def _model(row) -> None:
    st.subheader("Model")
    floor = row.get("training_week_floor")
    week = row.get("week")

    if pd.isna(row.get("predicted_margin")):
        # The two reasons a prediction is missing are completely different claims, and
        # collapsing them would be the site's worst kind of lie: "too early to say" versus
        # "we have nothing for this era".
        if pd.notna(floor) and pd.notna(week) and int(week) < int(floor):
            states.empty(
                "The model's forecast would be here.",
                f"Model predictions begin in Week {int(floor)}. The 2026 model needs "
                f"several weeks of current-season results before it can forecast this "
                f"year's teams, and this game is in Week {int(week)}.")
        else:
            states.empty(
                "The model's forecast would be here.",
                "No model has scored this game. Predictions cover 2025 from Week "
                f"{int(floor) if pd.notna(floor) else 5} onward.")
        return

    cols = st.columns(4)
    cols[0].metric("Predicted margin (home)",
                   fmt.signed(row.get("predicted_margin_home_perspective"), "margin"),
                   help="Positive means the model has the home team winning by that many.")
    cols[1].metric("Predicted total", fmt.number(row.get("predicted_total_points"), "total"))
    cols[2].metric("Home win probability",
                   fmt.number(row.get("home_win_probability"), "probability"))
    cols[3].metric("Cover edge", fmt.signed(row.get("home_cover_edge"), "edge"))

    if row.get("is_out_of_sample_week"):
        st.markdown(chips.out_of_sample_chip_html(True), unsafe_allow_html=True)

    st.caption(
        f"Model {row.get('model_name')} ({row.get('model_family')}), version "
        f"{row.get('model_version_key')}. Predicted score "
        f"{fmt.number(row.get('predicted_away_points'), '', 1)} – "
        f"{fmt.number(row.get('predicted_home_points'), '', 1)} (away – home).")

    actual = row.get("actual_margin_home_perspective")
    if pd.notna(actual):
        # Both readings come from the view. The app does not flip the sign: a sign
        # convention is a definition, and definitions live in dbt (G-3).
        st.caption(
            f"Actual margin {fmt.signed(actual, 'margin')} from the home perspective "
            f"({fmt.signed(row.get('actual_margin'), 'margin')} as cfdb stores it, away "
            f"minus home). Same result, read from the two ends.")
    attribution.model_attribution(pd.DataFrame([row]))


def _series(row) -> None:
    st.subheader("Head to head")
    games = row.get("series_games")
    if pd.isna(games) or int(games) == 0:
        states.empty("The series history would be here.",
                     "These teams have no previous meeting on record.")
        return
    home_wins, away_wins = row.get("series_home_team_wins"), row.get("series_away_team_wins")
    ties = row.get("series_ties")
    # Ties are counted, not inferred. The view used to derive the away record by
    # subtraction, which credited every draw to the away team.
    record = f"{int(home_wins)} – {int(away_wins)}"
    if pd.notna(ties) and int(ties):
        record += f" – {int(ties)}"
    st.markdown(
        f"**{row.get('home_team')} {record} {row.get('away_team')}** across {int(games)} "
        f"meeting{'s' if int(games) != 1 else ''}, "
        f"{int(row.get('series_first_season'))} to {int(row.get('series_last_season'))}.")
    if pd.notna(ties) and int(ties):
        st.caption(f"{int(ties)} of those ended in a tie — college football had no "
                   f"overtime before 1996.")


def render() -> None:
    shell.render_page("matchup", body)
