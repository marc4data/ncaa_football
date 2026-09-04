"""Today — page 1. The landing page: what is on, what the model likes.

Front of house only. No pipeline, dbt, freshness or DQ content appears here (AC-1.7) —
that is System Overview's job, back of house.
"""
import pandas as pd
import streamlit as st

from lib import attribution, chips, filters, fmt, shell, states, table
from lib.query import query
from lib.table import Col


def body(page) -> None:
    # F2-03: the bar renders on every data page, so a scope inherited from
    # another page is visible on arrival rather than silently in effect.
    scope = filters.game_scope()
    table.dataset_caption("Today", "srv_game")
    with states.section("srv_game"):
        df = query("""
            select game_id, season, week, season_type, start_date_et, venue_display,
                   is_neutral_site, network, home_team_slug, home_team_display,
                   home_logo_url, away_team_slug, away_team_display, away_logo_url,
                   spread_current, total_current, predicted_margin,
                   predicted_margin_home_perspective, home_win_probability,
                   market_implied_home_win_probability, devig_method, home_cover_edge,
                   confidence_bucket, is_out_of_sample_week, is_default_actionable,
                   training_week_floor,
                   model_version_key, attribution, excitement_index, as_of_ts
            from srv_game
            where (:season is null or season = :season)
              and (:week is null or week = :week)
            order by start_date_et, game_id
            limit 300
        """, {"season": scope.season, "week": scope.week})
        table.as_of_caption(df)
        _week_floor_note(df)

        only_predictions = st.toggle("Predictions only", value=False,
                                     help="Hide games with no model row")
        shown = df[df["predicted_margin"].notna()] if only_predictions else df

        # AC-1.1: an out-of-window query legitimately returns zero rows and must render
        # EMPTY, not Degraded — the view exists, there is simply no slate today.
        shown = table.apply_sort(shown, _columns(scope))
        states.render_or_state(
            shown, "srv_game",
            "Today's slate would be here.",
            f"No games in the current window for {scope.describe()}."
            + (" Try turning off “Predictions only”." if only_predictions else ""),
            renderer=lambda d: _slate(d, scope))

        if not shown.empty:
            attribution.model_attribution(shown)


def _week_floor_note(df: pd.DataFrame) -> None:
    """Say why the model column is empty, on the page most likely to be seen first.

    Today is a visitor's first stop and was the one page of the three that rendered the
    out-of-sample CHIP without ever explaining it. A chip on a blank cell is a label for an
    absence; the sentence is the reason for it.

    Rendered as a callout rather than a caption because this is prominent copy, not a
    footnote — it is a stated boundary of the model, and the strongest thing the project
    says about itself. A blank prediction block with no explanation is a broken site; the
    same block with this sentence is a working site with a boundary.

    The condition is the SLATE's, not today's date: a scope showing Week 2 explains itself
    whenever it is looked at, including in December when the model has long since started.
    """
    if df.empty or "training_week_floor" not in df.columns:
        return
    floors = df["training_week_floor"].dropna()
    if floors.empty:
        return
    floor = int(floors.min())
    below = df[df["week"].fillna(floor) < floor]
    if below.empty:
        return
    seasons = df["season"].dropna()
    st.info(chips.week_floor_note(
        floor, seasons.min() if not seasons.empty else None,
        clause=", so the model column is empty for these games"))


def _spread_and_model(row) -> str:
    """AC-1.4: a home favorite shows a NEGATIVE spread and a NEGATIVE predicted margin,
    and the two point the same way. This is the number most likely to be misread, so the
    convention is stated on the page rather than assumed."""
    spread = fmt.signed(row.get("spread_current"), "spread")
    pred = fmt.signed(row.get("predicted_margin"), "predicted_margin")
    return f"<span class='cfdb-num'>{spread}</span> · model {pred}"


def _slate(df: pd.DataFrame, scope) -> None:
    columns = _columns(scope)
    # F2-06: one layout for the whole slate, applied to every day group, so the same
    # column is the same width in every block on the page.
    layout = table.column_layout(df, columns)
    for day, rows in df.groupby(df["start_date_et"].dt.date, sort=True):
        st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B}</div>",
                    unsafe_allow_html=True)
        table.render(rows, columns, caption="", layout=layout,
                     link_builder=lambda r: scope.link("matchup", game_id=r["game_id"]))


def _columns(scope) -> list:
    return [
            Col("start_date_et", "Kickoff", "time"),
            Col("away", "Away", render=lambda r: table.team_cell(
                r, "away_team_slug", "away_team_display", "away_logo_url"),
                link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
            Col("home", "Home", render=lambda r: table.team_cell(
                r, "home_team_slug", "home_team_display", "home_logo_url"),
                link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
            # Named for what it renders, not for a real column. A synthetic Col whose name
            # collides with an actual field of the same view makes every field-keyed check
            # over these definitions ambiguous — the export's label comparison hit exactly
            # that against srv_edge_finder.market.
            Col("spread_and_model", "Spread · model", render=_spread_and_model),
            Col("total_current", "Total", "num"),
            Col("home_cover_edge", "Cover edge", "signed"),
            Col("flag", "", render=lambda r: chips.out_of_sample_chip_html(
                bool(r.get("is_out_of_sample_week")))),
            Col("network", "TV"),
            table.details_col(lambda r: scope.link("matchup", game_id=r["game_id"])),
    ]


def render() -> None:
    shell.render_page("today", body)
