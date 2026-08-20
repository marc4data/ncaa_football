"""Odds Board — page 11. Every book's current price, side by side.

The grain is (game, provider), so a game with three books is three rows and the reader
compares down the group rather than across a pivot. That is deliberate: pivoting to one row
per game with a column per book would need the app to reshape, and it would break the first
time a fourth book appeared.

`is_best_home_spread` / `is_best_away_spread` are computed in dbt and read here as flags.
"Best" is a definition — most favourable number available to a bettor taking that side —
and a definition belongs in the warehouse where it can be tested, not in a page.
"""
import pandas as pd
import streamlit as st

from lib import attribution, fmt, params, shell, states, table
from lib.query import query
from lib.table import Col


@st.cache_data(ttl=3600)
def _seasons() -> list:
    return query("select distinct season from srv_odds_board order by season desc limit 200"
                 )["season"].tolist()


@st.cache_data(ttl=900)
def _weeks(season: int) -> list:
    return query("""select distinct week from srv_odds_board
                    where season = :season order by week limit 40""",
                 {"season": season})["week"].tolist()


def body(page) -> None:
    with states.section("srv_odds_board"):
        seasons = _seasons()
        if not seasons:
            states.empty("The odds board would be here.",
                         "No betting lines have been loaded yet.")
            return

        requested = params.get("season")
        season = requested if requested in seasons else seasons[0]
        with st.sidebar:
            season = st.selectbox("Season", seasons, index=seasons.index(season))
            weeks = _weeks(season)
            options = ["All"] + [str(w) for w in weeks]
            current = str(params.get("week"))
            week_choice = st.selectbox("Week", options,
                                       index=options.index(current)
                                       if current in options else 0)
            best_only = st.toggle(
                "Best price only", value=False,
                help="Show only the book offering the most favourable number on each side.")

        week = None if week_choice == "All" else int(week_choice)
        params.set_params(season=season, week=week)

        df = query("""
            select game_id, season, week, season_type, start_date_et,
                   home_team_display, home_team_slug, home_logo_url,
                   away_team_display, away_team_slug, away_logo_url,
                   provider_key, provider_display, spread, spread_open, total, total_open,
                   home_moneyline, away_moneyline,
                   home_implied_probability, away_implied_probability, devig_method,
                   snapshot_ts, is_latest_snapshot,
                   predicted_margin, home_cover_edge,
                   is_best_home_spread, is_best_away_spread,
                   model_version_key, attribution, as_of_ts
            from srv_odds_board
            where season = :season
              and (:week is null or week = :week)
              and is_latest_snapshot
            order by start_date_et, game_id, provider_display
            limit 900
        """, {"season": season, "week": week})
        table.as_of_caption(df)

        if best_only and not df.empty:
            # Filtering is selection, not computation — the flags were decided in dbt.
            df = df[df["is_best_home_spread"].fillna(False)
                    | df["is_best_away_spread"].fillna(False)]

        states.render_or_state(
            df, "srv_odds_board",
            f"The {season} odds board would be here.",
            "No book has priced a game under the current filters."
            + (" Week filters narrow this quickly before the season starts."
               if week is not None else ""),
            renderer=_board,
            fix_label="Show every week" if week is not None else None,
            fix=lambda: (params.set_params(week=None), st.rerun()))

        if not df.empty:
            attribution.model_attribution(df)


def _best(row) -> str:
    """Which side this book currently prices best. Both is possible and is not a bug —
    one book can hold the best number on each side when the others are split."""
    home = bool(row.get("is_best_home_spread"))
    away = bool(row.get("is_best_away_spread"))
    if home and away:
        return "both"
    if home:
        return "home"
    if away:
        return "away"
    return fmt.EM_DASH


def _moneyline(field: str):
    """Moneylines are integers and must never pick up the site's 1-dp default.

    −270 rendering as −270.0 is not merely ugly; a price with a decimal point reads like a
    spread, and those are different quantities.
    """
    def render(row) -> str:
        value = row.get(field)
        if value is None or pd.isna(value):
            return fmt.EM_DASH
        return f"+{int(value)}" if int(value) > 0 else f"{int(value)}"
    return render


def _board(df: pd.DataFrame) -> None:
    columns = [
        Col("provider_display", "Book"),
        Col("spread", "Spread", "signed"),
        Col("spread_open", "Open", "signed"),
        Col("total", "Total", "num"),
        Col("home_ml", "Home ML", render=_moneyline("home_moneyline")),
        Col("away_ml", "Away ML", render=_moneyline("away_moneyline")),
        Col("home_implied_probability", "Home implied", "num"),
        Col("best", "Best", render=_best),
    ]
    for game_id, rows in df.groupby("game_id", sort=False):
        head = rows.iloc[0]
        st.markdown(
            f"<div class='cfdb-daygroup'>{head['away_team_display']} at "
            f"{head['home_team_display']} · {fmt.eastern(head['start_date_et'])}</div>",
            unsafe_allow_html=True)
        table.render(rows, columns, caption="srv_odds_board")
        if pd.notna(head.get("predicted_margin")):
            st.caption(
                f"Model margin {fmt.signed(head['predicted_margin'], 'margin')} "
                f"(away minus home), cover edge "
                f"{fmt.signed(head.get('home_cover_edge'), 'edge')}. "
                f"Implied probabilities de-vigged by {head.get('devig_method')}.")
        else:
            st.caption(
                f"No model row for this game yet. Implied probabilities de-vigged by "
                f"{head.get('devig_method') or 'the recorded method'}.")
        st.markdown(
            f"<a href='{params.link('matchup', game_id=int(game_id))}'>Matchup detail</a>",
            unsafe_allow_html=True)


def render() -> None:
    shell.render_page("odds", body)
