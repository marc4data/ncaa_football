"""Today — Looking Back. The weekly recap.

Front of house only. No pipeline, dbt, freshness or DQ content appears here (AC-1.7) — that
is System Overview's job, back of house.

WHAT THIS PAGE STOPPED BEING (R-428). It used to render an srv_game slate table, which
duplicated Schedule and answered a question Schedule answers better. The slate is not lost:
the link below routes to it. Today is now a recap of a COMPLETED week, and Looking Forward —
the week preview — is a later round and says so rather than showing an empty frame.

EVERY PANEL READS ONE SERVING VIEW AND DOES NO ARITHMETIC. The recap lists rank on columns
that already exist (`spread_favorite_side`, `moneyline_favorite_side`, `actual_margin`,
`favorite_covered`); the leaderboards order by a stored `stat_value`. Deriving a favorite or
a cover in Streamlit would be metric maths in the app, which is the rule those columns exist
to keep.
"""
import pandas as pd
import streamlit as st

from lib import attribution, filters, shell, states, table
from lib.query import query
from lib.table import Col

# Model-derived framing is withheld before the week named here, which is
# `prediction_training_week_floor`. The
# recap is market-only until then and says which, rather than showing an empty model column.
MODEL_WEEK_FLOOR = 5

# A user radio rather than a constant, so the page never pulls a whole leaderboard table.
DEPTHS = (10, 25, 50)

POLLS = ("AP Top 25", "Coaches Poll")


# --- data -----------------------------------------------------------------------------

def _completed_games(scope) -> pd.DataFrame:
    """Every completed game in scope. Feeds Most Exciting and all three recap lists."""
    return query("""
        select game_id, season, week, season_type, game_date,
               home_team_display, away_team_display, home_team_slug, away_team_slug,
               home_logo_url, away_logo_url, home_conference, away_conference,
               home_points, away_points, actual_margin, excitement_index,
               spread_at_close, spread_current, spread_open, spread_move_from_open,
               favorite_covered, spread_favorite_side, moneyline_favorite_side,
               favorite_definitions_disagree,
               market_implied_home_win_probability, market_implied_away_win_probability,
               lead_changes, largest_single_play_swing, home_win_probability_range,
               as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        order by excitement_index desc nulls last, game_id
        limit 400
    """, {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
          "conf": scope.conference, "division": scope.division})


def _team_yardage(scope, depth: int) -> pd.DataFrame:
    return query("""
        select team_display, team_slug, conference, opponent, week,
               total_yards, rushing_yards, passing_yards, points_for, result, as_of_ts
        from srv_team_game_log
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or classification = 'fbs')
          and (:conf is null or conference = :conf)
          and total_yards is not null
        order by total_yards desc, team_display
        limit {DEPTH}
    """.replace("{DEPTH}", str(int(depth))),
        {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
         "conf": scope.conference, "division": scope.division})


def _player_board(scope, depth: int, categories, stat_type: str) -> pd.DataFrame:
    """One leaderboard over srv_player_game_log.

    ⚠️ NO CLASSIFICATION COLUMN ON THIS VIEW, so `division` cannot be applied here the way it
    is on the team board — see the report. Conference still filters.
    """
    return query("""
        select player_name, player_slug, team, conference, opponent, week,
               stat_category, stat_type, stat_value, as_of_ts
        from srv_player_game_log
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and stat_type = :stat_type
          and stat_category = any(:cats)
          and (:conf is null or conference = :conf)
          and stat_value is not null
        order by stat_value desc, player_name
        limit {DEPTH}
    """.replace("{DEPTH}", str(int(depth))),
        {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
         "conf": scope.conference, "cats": list(categories), "stat_type": stat_type})


def _rankings(scope) -> pd.DataFrame:
    """Full season of AP and Coaches, for the bump chart and its companion table."""
    return query("""
        select season, week, poll_name, rank, team_display, team_slug,
               first_place_votes, points, as_of_ts
        from srv_rankings
        where season = :season and season_type = :season_type
          and poll_name = any(:polls)
        order by poll_name, week, rank
        limit 2000
    """, {"season": scope.season, "season_type": scope.season_type, "polls": list(POLLS)})


# --- panels ---------------------------------------------------------------------------

def _most_exciting(df: pd.DataFrame, scope) -> None:
    st.subheader("Most exciting")
    st.caption(
        "CFBD's excitement index, shown as published — not re-scaled. "
        "Source: [CollegeFootballData.com](https://collegefootballdata.com).")
    top = df[df["excitement_index"].notna()].head(10)
    states.render_or_state(
        top, "srv_game",
        "The week's most exciting games would be here.",
        f"No completed games with an excitement index for {scope.describe()}.",
        renderer=lambda d: table.render(d, [
            Col("matchup", "Game", fmt=lambda r: f"{r.away_team_display} at {r.home_team_display}"),
            Col("score", "Score", fmt=lambda r: f"{int(r.away_points)}–{int(r.home_points)}"
                if pd.notna(r.away_points) else "—"),
            Col("excitement_index", "Excitement", kind="num", decimals=1),
            Col("lead_changes", "Lead changes", kind="num"),
        ], caption="Ranked by CFBD excitement index."))


def _recap_lists(df: pd.DataFrame, scope) -> None:
    st.subheader("How the week went against the market")
    if scope.week is not None and scope.week < MODEL_WEEK_FLOOR:
        st.caption(
            f"Market-only edition. Model-derived framing is withheld before week "
            f"{MODEL_WEEK_FLOOR} because the season has not trained enough games to say "
            f"anything honest; these three lists are the closing market and the result.")

    graded = df[df["spread_favorite_side"].notna() & df["actual_margin"].notna()].copy()
    if graded.empty:
        states.empty("The recap lists would be here.",
                     f"No graded games with a closing line for {scope.describe()}.")
        return

    # Ranking columns, carried not derived. `favorite_covered` and `actual_margin` come from
    # the view; all this does is order rows and pick a side's label to show.
    graded["favorite"] = graded.apply(
        lambda r: r.home_team_display if r.spread_favorite_side == "home"
        else r.away_team_display, axis=1)
    graded["opponent"] = graded.apply(
        lambda r: r.away_team_display if r.spread_favorite_side == "home"
        else r.home_team_display, axis=1)
    graded["fav_margin"] = graded.apply(
        lambda r: r.actual_margin if r.spread_favorite_side == "home" else -r.actual_margin,
        axis=1)
    graded["spread"] = graded["spread_at_close"].fillna(graded["spread_current"]).abs()
    graded["ats"] = graded["fav_margin"] - graded["spread"]
    graded["fav_win_prob"] = graded.apply(
        lambda r: r.market_implied_home_win_probability if r.spread_favorite_side == "home"
        else r.market_implied_away_win_probability, axis=1)

    missed = graded[graded["ats"] < 0].sort_values("ats").head(10)
    lost = graded[graded["fav_margin"] < 0].sort_values(
        "fav_win_prob", ascending=False, na_position="last").head(10)
    covers = graded[graded["ats"] < 0].sort_values("ats").head(10)

    cols = [Col("favorite", "Favorite"), Col("opponent", "Opponent"),
            Col("spread", "Spread", kind="num", decimals=1),
            Col("fav_margin", "Margin", kind="num"),
            Col("ats", "vs spread", kind="num", decimals=1)]

    st.markdown("**Underperformers — by points missed against the closing spread**")
    table.render(missed, cols, caption="Favorites, ranked by how far short of the number they finished.")

    st.markdown("**Underperformers — by how likely the market thought they were to win**")
    table.render(lost, cols + [Col("fav_win_prob", "Win prob", kind="num", decimals=3)],
                 caption="Favorites that lost outright, ranked by pregame market-implied win probability.")

    st.markdown("**Biggest underdog covers**")
    st.caption(
        "⚠️ This is the same set of games as the first list, read from the other side: a "
        "favorite missing by X is the underdog covering by X. Both are shown because the "
        "reader's question differs — who disappointed, and who was undervalued.")
    table.render(covers.assign(underdog=covers["opponent"], beat=covers["ats"].abs()),
                 [Col("underdog", "Underdog"), Col("favorite", "Favorite"),
                  Col("spread", "Getting", kind="num", decimals=1),
                  Col("beat", "Covered by", kind="num", decimals=1)],
                 caption="The mirror of the first list.")

    disagree = int(graded["favorite_definitions_disagree"].fillna(False).sum())
    if disagree:
        st.caption(
            f"⚠️ In {disagree} of these games the spread and the moneyline named different "
            "favorites. The first and third lists use the spread; the second uses the "
            "moneyline, because that is what an implied win probability comes from.")


def _leaderboards(scope, depth: int) -> None:
    st.subheader("Leaderboards")

    with states.section("srv_team_game_log"):
        teams = _team_yardage(scope, depth)
        st.markdown("**Team yardage**")
        states.render_or_state(
            teams, "srv_team_game_log",
            "The team yardage board would be here.",
            f"No completed team box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda d: table.render(d, [
                Col("team_display", "Team"), Col("opponent", "Opponent"),
                Col("total_yards", "Total", kind="num"),
                Col("rushing_yards", "Rush", kind="num"),
                Col("passing_yards", "Pass", kind="num"),
            ], caption="Ranked by total offense."))

    with states.section("srv_player_game_log"):
        yards = _player_board(scope, depth, ("passing", "rushing", "receiving"), "YDS")
        st.markdown("**Player yardage**")
        states.render_or_state(
            yards, "srv_player_game_log",
            "The player yardage board would be here.",
            f"No player box scores for {scope.describe()}. Box scores start in 2024.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("stat_category", "Category"),
                Col("stat_value", "Yards", kind="num"),
            ], caption="Passing, rushing and receiving yards in one board."))

        tds = _player_board(scope, depth, ("passing", "rushing", "receiving"), "TD")
        st.markdown("**Touchdowns**")
        st.caption("A different board from yardage, and mostly different names on it.")
        states.render_or_state(
            tds, "srv_player_game_log",
            "The touchdown board would be here.",
            f"No player box scores for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("stat_category", "Category"),
                Col("stat_value", "TD", kind="num"),
            ], caption="Passing, rushing and receiving touchdowns."))

        st.markdown("**Defensive leaders**")
        defence = _player_board(scope, depth, ("defensive",), "TOT")
        states.render_or_state(
            defence, "srv_player_game_log",
            "The defensive board would be here.",
            f"No defensive box scores for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("player_name", "Player"), Col("team", "Team"),
                Col("opponent", "Opponent"),
                Col("stat_value", "Tackles", kind="num"),
            ], caption="Total tackles. TFL and sacks are separate stat types on the same view."))


def _bump(scope) -> None:
    st.subheader("Poll movement")
    with states.section("srv_rankings"):
        polls = _rankings(scope)
        if polls.empty:
            states.empty("The poll chart would be here.",
                         f"No AP or Coaches poll rows for {scope.describe()}.")
            return
        poll = st.radio("Poll", POLLS, horizontal=True, key="today_poll")
        one = polls[polls["poll_name"] == poll]
        if one.empty:
            states.empty("The poll chart would be here.", f"No {poll} rows for this season.")
            return

        chart = one.pivot_table(index="week", columns="team_display", values="rank")
        st.line_chart(chart, height=380)
        st.caption(f"{poll}, full season. Rank 1 at the top of the axis is inverted by "
                   "convention; every ranked team is drawn.")

        latest_week = int(one["week"].max())
        current = one[one["week"] == latest_week].copy()
        previous = one[one["week"] == latest_week - 1][["team_display", "rank"]]
        previous = previous.rename(columns={"rank": "prev_rank"})
        current = current.merge(previous, on="team_display", how="left")

        # ⚠️ A team with no previous rank is NEW or RETURNING, never "no change". Rendering
        # that as 0 or blank is the defect this column exists to avoid.
        def _delta(row) -> str:
            if pd.isna(row.prev_rank):
                return "new" if latest_week == int(one["week"].min()) else "unranked last week"
            change = int(row.prev_rank) - int(row["rank"])
            return "—" if change == 0 else (f"▲ {change}" if change > 0 else f"▼ {abs(change)}")

        current["delta"] = current.apply(_delta, axis=1)
        table.render(current.sort_values("rank"), [
            Col("rank", "Rank", kind="num"),
            Col("team_display", "Team"),
            Col("points", "Points", kind="num"),
            Col("delta", "vs previous week"),
        ], caption=f"{poll}, week {latest_week}. Points are the poll total; first-place votes "
                   "are carried separately on the view.")


def _looking_forward(scope) -> None:
    st.subheader("Looking forward")
    st.caption(
        "The week preview — matchups to watch, and what the market makes of them — is the "
        "next round of work on this page. It is not built yet, and an empty frame would "
        "imply it was.")
    st.markdown(f"For the full slate, see [Schedule]({scope.link('schedule')}).")


# --- page -----------------------------------------------------------------------------

def body(page) -> None:
    scope = filters.game_scope()
    table.dataset_caption("Looking Back", "srv_game")

    depth = st.radio("Leaderboard depth", DEPTHS, index=1, horizontal=True,
                     key="today_depth", help="How many rows each leaderboard shows.")

    with states.section("srv_game"):
        games = _completed_games(scope)
        table.as_of_caption(games)

        if games.empty:
            states.empty(
                "The weekly recap would be here.",
                f"No completed games for {scope.describe()}. "
                "Pick a week that has finished, or widen the conference filter.")
        else:
            _most_exciting(games, scope)
            _recap_lists(games, scope)

    _leaderboards(scope, depth)
    _bump(scope)
    _looking_forward(scope)

    if not _completed_games(scope).empty:
        attribution.model_attribution(_completed_games(scope))


def render() -> None:
    shell.page(body)
