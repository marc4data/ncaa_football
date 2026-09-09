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


def _line_movement(scope) -> pd.DataFrame:
    """Every completed game in scope with its line-movement columns, ranked in the panel.

    ⚠️ NOT FILTERED TO GAMES THAT MOVED. The panel needs the games with NO snapshots in order
    to say how many it is not showing — a list that silently shortens is the fallback-at-100%
    defect, and the count is only knowable here. So this reads the scope and the panel does
    the ranking and the arithmetic of what it dropped.

    ⚠️ THERE ARE TEN `line_*` COLUMNS, NOT ELEVEN. A074's prompt and INDEX.md both say
    eleven; counted from published serving's information_schema on 2026-09-09 it is ten, and
    `line_snapshot_ts` is the tenth (not read here). The likely source of the miscount is that
    `srv_game` ALSO carries older unprefixed `spread_move_from_open` and `total_move_from_open`
    from before B070 — different columns with confusable names. The nine selected below are
    read as published; nothing here derives a movement figure.
    """
    return query("""
        select game_id, home_team_display, away_team_display,
               line_spread_largest_excursion, line_spread_move_from_open,
               line_total_largest_excursion, line_total_move_from_open,
               line_market_implied_win_probability_largest_excursion,
               line_market_implied_win_probability_move_from_open,
               line_snapshot_count, line_movement_spans_snapshot_gap,
               line_movement_provider_key, as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          and is_completed
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        order by game_id
        limit 400
    """, {"season": scope.season, "week": scope.week, "season_type": scope.season_type,
          "conf": scope.conference, "division": scope.division})


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
            Col("matchup", "Game", render=lambda r: f"{r.away_team_display} at {r.home_team_display}"),
            Col("score", "Score", render=lambda r: f"{int(r.away_points)}–{int(r.home_points)}"
                if pd.notna(r.away_points) else "—"),
            Col("excitement_index", "Excitement", kind="num", dp=1),
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
            Col("spread", "Spread", kind="num", dp=1),
            Col("fav_margin", "Margin", kind="num"),
            Col("ats", "vs spread", kind="num", dp=1)]

    st.markdown("**Underperformers — by points missed against the closing spread**")
    table.render(missed, cols, caption="Favorites, ranked by how far short of the number they finished.")

    st.markdown("**Underperformers — by how likely the market thought they were to win**")
    table.render(lost, cols + [Col("fav_win_prob", "Win prob", kind="num", dp=3)],
                 caption="Favorites that lost outright, ranked by pregame market-implied win probability.")

    st.markdown("**Biggest underdog covers**")
    st.caption(
        "⚠️ This is the same set of games as the first list, read from the other side: a "
        "favorite missing by X is the underdog covering by X. Both are shown because the "
        "reader's question differs — who disappointed, and who was undervalued.")
    table.render(covers.assign(underdog=covers["opponent"], beat=covers["ats"].abs()),
                 [Col("underdog", "Underdog"), Col("favorite", "Favorite"),
                  Col("spread", "Getting", kind="num", dp=1),
                  Col("beat", "Covered by", kind="num", dp=1)],
                 caption="The mirror of the first list.")

    disagree = int(graded["favorite_definitions_disagree"].fillna(False).sum())
    if disagree:
        st.caption(
            f"⚠️ In {disagree} of these games the spread and the moneyline named different "
            "favorites. The first and third lists use the spread; the second uses the "
            "moneyline, because that is what an implied win probability comes from.")


def _movers(scope, depth: int) -> None:
    """R-475. The week's games ranked by how far the line travelled.

    ⚠️ RANKED BY LARGEST EXCURSION, NOT BY NET MOVE, and that is the whole point of the
    panel. A059 measured that excursion exceeds net move at every decile and that roughly a
    third of games END WHERE THEY STARTED having moved in between — so a ranking on net move
    hides precisely the games worth looking at. Both numbers are shown; only the excursion
    orders the list.

    ⚠️ NO THRESHOLD, NO COLOUR SCALE, NO "BIG MOVER" BADGE. A059 measured the distributions
    and deliberately stopped there: Marc sets the line, not the page. This shows the ranked
    list and the numbers.

    ⚠️ THE EXCURSION IS SIGNED, so the ranking is on its MAGNITUDE while the displayed value
    keeps its direction — a 6-point move toward the home side and one toward the away side
    are equally far travelled and belong equally high on the list.

    ⚠️ THE WIN-PROBABILITY COLUMNS ARE ALREADY IN PROBABILITY POINTS. Measured on published
    serving 2026 wk1: `market_implied_home_win_probability` runs 0.068…0.98 while
    `line_market_implied_win_probability_largest_excursion` runs -13.4…+10.6. They do NOT
    share a scale. Multiplying this one by 100 — the obvious thing to do to a column whose
    name says "probability" — renders 1,338 points and looks merely large rather than wrong.
    """
    st.subheader("The week's movers")

    with states.section("srv_game"):
        games = _line_movement(scope)
        if games.empty:
            states.empty(
                "The week's line movement would be here.",
                f"No completed games for {scope.describe()}.")
            return

        moved = games[games["line_spread_largest_excursion"].notna()]
        # THE THREE POPULATIONS, kept apart because they are different facts. A game with one
        # snapshot is not a game with no snapshots: the first was priced and never re-priced,
        # the second was never seen. Collapsing them into "no data" would overstate the hole.
        no_snapshots = int((games["line_snapshot_count"].fillna(0) == 0).sum())
        too_few = len(games) - len(moved) - no_snapshots

        # THE BOOK, READ FROM THE DATA RATHER THAN NAMED IN A LITERAL. These figures are
        # DraftKings-only by construction, and a movement number without its source is the
        # provenance defect the `market_implied_` prefix rule exists to prevent. Reading it
        # from the column means the caption cannot drift from what was actually priced.
        books = sorted({str(b) for b in moved["line_movement_provider_key"].dropna().unique()})
        book = ", ".join(books) if books else "an unnamed book"

        dropped = []
        if no_snapshots:
            dropped.append(f"{no_snapshots} had no line snapshots")
        if too_few:
            dropped.append(f"{too_few} had too few to measure a move")
        tail = f" Of {len(games)} completed games, {' and '.join(dropped)}." if dropped else ""

        st.caption(
            f"Ranked by the largest distance the spread travelled at any point, not by where "
            f"it finished — about a third of games end where they opened having moved in "
            f"between. Prices from {book}.{tail}")

        # mergesort because it is STABLE: games tied on excursion — and ties are common,
        # since spreads move in half and whole points — keep the query's game_id order
        # instead of reshuffling between renders of the same week.
        by_distance = moved["line_spread_largest_excursion"].abs()
        order = by_distance.sort_values(ascending=False, kind="mergesort").index
        ranked = moved.reindex(order).head(depth)

        # ⚠️ ON A SINGLE-SNAPSHOT GAME THE EXCURSION EQUALS THE NET MOVE BY CONSTRUCTION.
        # 2024 and 2025 were backfilled one row per game, so for those rows the two numbers
        # this panel shows side by side are the same measurement twice — and the caption's
        # "furthest it travelled, not where it finished" is not true of them. matchup.py's
        # own panel says this for one game; a ranked list needs to say it too, or the reader
        # ranks a week of 2025 believing they are looking at round trips that were never
        # observed. Said only when such a row is actually on screen.
        single = int((ranked["line_snapshot_count"].fillna(0) <= 1).sum())
        caveat = (f" {single} of these were priced once, so their furthest and net figures "
                  f"are the same number by construction rather than by measurement."
                  if single else "")

        states.render_or_state(
            ranked,
            "srv_game",
            "The week's line movement would be here.",
            f"No games with enough line snapshots to measure a move for {scope.describe()}.",
            renderer=lambda d: table.render(d, [
                Col("matchup", "Game",
                    render=lambda r: f"{r.away_team_display} at {r.home_team_display}"),
                Col("line_spread_largest_excursion", "Spread — furthest", kind="signed", dp=1),
                Col("line_spread_move_from_open", "Spread — net", kind="signed", dp=1),
                Col("line_total_largest_excursion", "Total — furthest", kind="signed", dp=1),
                Col("line_market_implied_win_probability_largest_excursion",
                    "Win prob — furthest (pp)", kind="signed", dp=1),
                # dp=0 BECAUSE THE FRAME FLOATS IT. line_snapshot_count is a bigint in
                # serving, but games with no snapshots put NaN in the column and pandas
                # widens the whole thing to float64 — so the default rendered "94.0" against
                # real data and "94" against any fixture without a null in it. Measured on
                # published serving, not reasoned about.
                Col("line_snapshot_count", "Snapshots", kind="num", dp=0),
                # ⚠️ PER ROW, NOT A FOOTNOTE. A window that spans a snapshot gap makes THAT
                # game's excursion a FLOOR rather than a measurement — the line may have gone
                # further while nobody was looking. 98 of 171 priced games in 2026 wk1 span
                # one, so a footnote would be describing the majority of the list.
                Col("line_movement_spans_snapshot_gap", "Window",
                    # ⚠️ NO APOSTROPHE IN THE TITLE, AND DOUBLE QUOTES AROUND IT. The first
                    # version wrote title='This game\'s prices…', whose apostrophe CLOSED the
                    # attribute mid-sentence and spilled the rest into the tag as stray
                    # attributes. It looked correct in the source and was only visible in
                    # rendered output against real rows.
                    render=lambda r: (
                        '<span title="Prices for this game have a gap in them, so the '
                        'distance shown is a floor: the line may have travelled further '
                        'while it was unobserved.">has a gap</span>'
                        if r.get("line_movement_spans_snapshot_gap") else "complete")),
            ], caption=f"Spread and total in points; win probability in de-vigged "
                       f"probability points. Prices from {book}. A row marked "
                       f"\u201chas a gap\u201d is a floor, not a measurement.{caveat}"))


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

    _movers(scope, depth)
    _leaderboards(scope, depth)
    _bump(scope)
    _looking_forward(scope)

    if not _completed_games(scope).empty:
        attribution.model_attribution(_completed_games(scope))


def render() -> None:
    # R-479. `shell.page` DOES NOT EXIST — the module exports render_page(key, body), and the
    # other fourteen views all call it that way. This line raised AttributeError on every
    # open from A067 (c2f5b50, #143, 2026-09-08) until 2026-09-09, and Today is app.py's
    # DEFAULT page, so it was the first thing every visitor hit.
    #
    # Nothing in the repo could see it. test_site_foundation IMPORTS every view module, which
    # succeeds — the name is only resolved when render() is called. The site-image smoke test
    # builds st.Page objects and counts them without running one. A074's panel-exercise test
    # calls the panels directly and never goes through render(). Every check was one layer
    # away from the only line that mattered. That gap is R-480.
    shell.render_page("today", body)
