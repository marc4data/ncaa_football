"""Line Movement — page 14. How a price changed between opening and now.

One game at a time, because movement is only legible against a fixed pair of teams. The
series is per (game, provider): two books that opened at the same number and moved apart
are the interesting case, and averaging them would destroy exactly that.

`spread_move_from_open` comes from the view. The app could subtract two columns, and that
is precisely why it does not — a movement figure is a definition (which snapshot counts as
"open"), and definitions live in dbt.
"""
import pandas as pd
import streamlit as st

from lib import filters, fmt, params, shell, states, table
from lib.query import query
from lib.table import Col


@st.cache_data(ttl=3600)
def _seasons() -> list:
    return query("select distinct season from srv_line_movement order by season desc limit 200"
                 )["season"].tolist()


@st.cache_data(ttl=900)
def _games(season: int, week) -> pd.DataFrame:
    """The games that have any line history, for the picker.

    `select distinct` rather than a group-by with a snapshot count. The count would pass
    the query contract — one relation, no join — but a snapshot tally in a dropdown label
    is a figure nobody asked for, and every number on screen is one more thing that has to
    be right.
    """
    return query("""
        select distinct game_id, week, game_date, home_team, away_team
        from srv_line_movement
        where season = :season and (:week is null or week = :week)
        order by game_date, game_id
        limit 400
    """, {"season": season, "week": week})


def body(page) -> None:
    # F2-03: the bar renders on every data page, so a scope inherited from
    # another page is visible on arrival rather than silently in effect.
    scope = filters.game_scope()
    table.dataset_caption("Line movement", "srv_line_movement")
    with states.section("srv_line_movement"):
        seasons = _seasons()
        if not seasons:
            states.empty("Line movement would be here.",
                         "No betting-line snapshots have been recorded yet.")
            return

        season, week = scope.season, scope.week
        games = _games(season, week)
        if games.empty:
            states.empty(
                "Line movement would be here.",
                f"No book priced a game in {season}"
                + (f" week {week}." if week is not None else "."),
                fix_label="Show every week" if week is not None else None,
                fix=lambda: (params.set_params(week=None), st.rerun()))
            return

        labels = [f"{r.away_team} at {r.home_team} — wk {int(r.week)}"
                  for r in games.itertuples()]
        ids = games["game_id"].tolist()
        chosen = params.get("game_id")
        label = st.selectbox("Game", labels,
                             index=ids.index(chosen) if chosen in ids else 0)
        game_id = int(ids[labels.index(label)])
        params.set_params(game_id=game_id)

        df = query("""
            select game_id, snapshot_ts, provider_key, provider_name, season, week,
                   spread, spread_open, spread_move_from_open,
                   over_under, over_under_open, home_moneyline, away_moneyline,
                   game_date, home_team, away_team, as_of_ts
            from srv_line_movement
            where game_id = :game_id
            order by snapshot_ts, provider_name
            limit 500
        """, {"game_id": game_id})
        table.as_of_caption(df)

        if df.empty:
            states.empty("This game's line history would be here.",
                         f"No snapshots recorded for game {game_id}.")
            return

        head = df.iloc[0]
        st.subheader(f"{head['away_team']} at {head['home_team']}")
        _chart(df)
        _summary(df)
        table.render(df, [
            Col("snapshot_ts", "Snapshot", "datetime"),
            Col("provider_name", "Book"),
            Col("spread", "Spread", "signed"),
            Col("spread_open", "Open", "signed"),
            Col("spread_move_from_open", "Move", "signed"),
            Col("over_under", "Total", "num"),
        ], caption="srv_line_movement", max_rows=200)


def _chart(df: pd.DataFrame) -> None:
    """Spread over time, one line per book.

    A pivot for plotting is reshaping, not computing: every value drawn is a value the view
    returned, unchanged. Nothing here derives a number that was not already in the frame.
    """
    series = df.pivot_table(index="snapshot_ts", columns="provider_name",
                            values="spread", aggfunc="last")
    if series.empty or len(series) < 2:
        st.caption("Only one snapshot so far — a line needs two points to move.")
        return
    st.line_chart(series, height=240)
    st.caption("Spread from the home perspective; a falling line means the home team is "
               "being bet.")


def _summary(df: pd.DataFrame) -> None:
    """Per book, where it opened and where it is now. Read, not recomputed."""
    latest = df.sort_values("snapshot_ts").groupby("provider_name").tail(1)
    columns = st.columns(min(len(latest), 4) or 1)
    for column, (_, row) in zip(columns, latest.iterrows()):
        column.metric(
            row["provider_name"],
            fmt.signed(row.get("spread"), "spread"),
            delta=(fmt.signed(row.get("spread_move_from_open"), "spread")
                   if pd.notna(row.get("spread_move_from_open")) else None),
            help=f"Opened {fmt.signed(row.get('spread_open'), 'spread')}.")


def render() -> None:
    shell.render_page("movement", body)
