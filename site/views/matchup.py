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

from lib import (attribution, chips, filters, fmt, identity, params, shell,
                 states, table)
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
    with states.section("srv_game"):
        game_id = params.get("game_id")
        if game_id is None:
            _picker()
            return

        df = query(f"""
            select {COLUMNS}
            from srv_game
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
        # Its own view and its own section: weather exists for 2024 onward only, and a
        # nested section means a weather failure degrades one block rather than blanking a
        # page that is otherwise complete.
        _weather(game_id)
        _travel(game_id)


def _picker() -> None:
    """No game_id. A REAL PICKER, not an arbitrary list.

    Arriving here cold used to show the most recent 300 games sorted by date with no way to
    narrow them — an unfiltered list, which is not a decision surface but a broken index.
    That only became visible because nothing on the site linked to this page, so the nav
    entry was the sole route in; with the deep links working it is the exception rather
    than the way in.

    Keeping the nav slot and giving it a job: the same filter bar every other page uses,
    grouped by day, searchable by team. AC-10.1 as amended.
    """
    scope = filters.game_scope()
    table.dataset_caption("Matchup", "srv_game")
    st.markdown("Pick a game to see the full matchup — market, model, and the series "
                "history. Every game row elsewhere on the site links straight here.")
    search = st.text_input("Find a team", placeholder="Type a team name…")

    games = query("""
        select game_id, season, week, start_date_et, game_date,
               home_team, away_team, home_conference, away_conference,
               home_points, away_points, is_completed, venue_display
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and (:conference is null or home_conference = :conference
               or away_conference = :conference)
        order by start_date_et, game_id
        limit 400
    """, {"season": scope.season, "season_type": scope.season_type,
          "week": scope.week, "conference": scope.conference})

    if search and not games.empty:
        mask = (games["home_team"].str.contains(search, case=False, na=False)
                | games["away_team"].str.contains(search, case=False, na=False))
        games = games[mask]

    states.render_or_state(
        games, "srv_game",
        "Games would be listed here.",
        f"No game matches “{search}”." if search else
        f"No games recorded for {scope.describe()}.",
        renderer=lambda d: _picker_table(d, scope),
        fix_label="Clear filters" if (scope.week or scope.conference) else None,
        fix=filters.clear)


def _picker_table(df, scope) -> None:
    """Grouped by day, like every other game list on the site."""
    for day, rows in df.groupby(df["game_date"], sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{fmt.day(pd.Timestamp(day))}</div>",
                    unsafe_allow_html=True)
        table.render(rows, [
            Col("start_date_et", "Kickoff", "time"),
            Col("away_team", "Away"),
            Col("away_points", "", "num", dp=0),
            Col("home_team", "Home"),
            Col("home_points", "", "num", dp=0),
            Col("venue_display", "Venue"),
        ], caption="",
            link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


def _scoreline(row) -> None:
    """Both teams, their colours, and the score if there is one.

    A scheduled game shows no score rather than 0–0. Two zeroes is a real result — a
    scoreless tie — and rendering an unplayed game the same way asserts something false.
    """
    played = bool(row.get("is_completed"))
    # AWAY on the LEFT, HOME on the right — the universal convention, and the reason the
    # previous layout read as unnatural. "Team, venue, team" is not a matchup; "away @ home"
    # is how every scoreboard in the sport is written.
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
            f"<strong>@</strong><br>"
            f"{'Final' if played else 'Scheduled'}<br>"
            f"{fmt.local_time(row.get('start_date_et'))}"
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
    # AC-1.4 again: a home favorite is a NEGATIVE spread. Stated on the page, because this
    # is the number a reader is most likely to invert.
    cols[0].metric("Spread (home)", fmt.signed(row.get("spread"), "spread"),
                   help="Negative means the home team is favoured.")
    # R-009, third placement. Same sentence, one source.
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
    chips.spread_sign_note()
    st.caption(f"Line from {row.get('provider_key') or 'an unnamed book'}, "
               f"snapshot {fmt.local_time(row.get('line_snapshot_ts'))}. "
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
                chips.week_floor_note(
                    floor, row.get("season"),
                    clause=f", and this game is in Week {int(week)}"))
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


def _weather(game_id) -> None:
    """Conditions at kickoff, from srv_game_weather.

    THE INDOOR CAVEAT IS NOT DECORATION. CFBD reports the weather at the venue's LOCATION,
    not inside it, so domed games carry ordinary outdoor readings — 10°F to 98°F, 9 mph
    average wind, and five with measurable precipitation. Rendering "Rain, 41°F" for a game
    played under a roof would be stating something false, so the roof is said first and the
    readings are labelled as outside.
    """
    st.subheader("Weather")
    with states.section("srv_game_weather"):
        df = query("""
            select game_id, season, venue, city, state, is_indoors, temperature_f,
                   humidity_pct, precipitation_in, snowfall_in, wind_speed_mph,
                   wind_direction_compass, weather_condition, is_precipitating,
                   elevation_m, as_of_ts
            from srv_game_weather
            where game_id = :game_id
            limit 1
        """, {"game_id": game_id})
        if df.empty:
            states.empty(
                "Conditions at kickoff would be here.",
                "Weather is collected from 2024 onward, and not every game has a reading.")
            return

        row = df.iloc[0]
        indoors = bool(row.get("is_indoors"))
        if indoors:
            st.caption(
                f"{row.get('venue')} is indoors. The readings below are the outdoor "
                "conditions at the venue's location and did not affect play.")

        def show(value, suffix=""):
            return "—" if value is None or pd.isna(value) else f"{value:g}{suffix}"

        cols = st.columns(4)
        cols[0].metric("Temperature", show(row.get("temperature_f"), "°F"))
        cols[1].metric("Wind", show(row.get("wind_speed_mph"), " mph")
                       + (f" {row.get('wind_direction_compass')}"
                          if row.get("wind_direction_compass") else ""))
        cols[2].metric("Humidity", show(row.get("humidity_pct"), "%"))
        cols[3].metric("Conditions", row.get("weather_condition") or "—")

        notes = []
        if pd.notna(row.get("precipitation_in")) and row.get("precipitation_in"):
            notes.append(f"{row['precipitation_in']:g} in precipitation")
        if pd.notna(row.get("snowfall_in")) and row.get("snowfall_in"):
            notes.append(f"{row['snowfall_in']:g} in snow")
        if pd.notna(row.get("elevation_m")):
            notes.append(f"venue elevation {row['elevation_m']:g} m")
        if notes:
            st.caption(" · ".join(notes))
        table.as_of_caption(df)


def _travel(game_id) -> None:
    """How far each side came and how long they had to rest.

    TWO MEASURES WITH DIFFERENT COVERAGE, shown separately rather than blended. Rest comes
    from the schedule and exists for every game that is not a season opener; travel needs
    coordinates for both venues, so it is 2024 onward and about 79% even there. A null
    distance renders as an em dash, never as zero — zero means they played at home.
    """
    st.subheader("Travel and rest")
    with states.section("srv_game_travel"):
        df = query("""
            select team, opponent, is_home, is_neutral_site, game_venue, travel_km,
                   elevation_change_m, rest_days, rest_bucket, previous_game_date, as_of_ts
            from srv_game_travel
            where game_id = :game_id
            order by is_home desc
            limit 2
        """, {"game_id": game_id})
        if df.empty:
            states.empty("How far each side travelled would be here.",
                         "No travel or rest figures for this game.")
            return

        for _, r in df.iterrows():
            side = "Home" if r.get("is_home") else "Away"
            if r.get("is_neutral_site"):
                side = "Neutral site"
            st.markdown(f"**{r.get('team')}** · {side}")
            cols = st.columns(3)
            km = r.get("travel_km")
            cols[0].metric(
                "Travel",
                # Zero is a real answer here and reads as one; null is not.
                "—" if km is None or pd.isna(km)
                else ("Home venue" if float(km) < 1 else f"{float(km):,.0f} km"))
            rest = r.get("rest_days")
            cols[1].metric(
                "Rest",
                "—" if rest is None or pd.isna(rest) else f"{int(rest)} days",
                help=str(r.get("rest_bucket") or ""))
            change = r.get("elevation_change_m")
            cols[2].metric(
                "Elevation change",
                # Signed on purpose: arriving 1,500 m higher and 1,500 m lower are
                # different experiences and a magnitude would erase which happened.
                "—" if change is None or pd.isna(change) else f"{float(change):+,.0f} m")
        table.as_of_caption(df)


def render() -> None:
    shell.render_page("matchup", body)
