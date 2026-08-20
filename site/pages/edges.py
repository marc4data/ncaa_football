"""Edge Finder — page 12. Where the model disagrees with the market, ranked by how much.

This is the only page in the site that has nothing to show for the first four weeks of a
season, and that is not a defect to hide. An edge is model minus market; the model cannot
forecast this year's teams until it has seen several weeks of this year's results, so weeks
1 to 4 have no edges to find. The page renders EMPTY and explains itself, per AC-G.51 —
Degraded would be a lie, because nothing is broken and nothing is missing that should exist.

The week floor is read from `training_week_floor`, a COLUMN. Hardcoding "Week 5" here would
put the model's training decision in a page file, where it would quietly go stale the first
time the model is retrained on a different cut.
"""
import pandas as pd
import streamlit as st

from lib import attribution, chips, fmt, params, shell, states, table
from lib.query import query
from lib.table import Col

MARKETS = {"Spread (points)": "spread", "Moneyline (probability)": "moneyline"}
BY_CODE = {code: label for label, code in MARKETS.items()}


@st.cache_data(ttl=3600)
def _floor() -> int:
    """The model's coverage floor, from the data rather than from this file.

    Read separately from the main query on purpose: when the page is empty the main frame
    carries no columns at all, and the floor is precisely what the Empty copy needs. A
    number the page cannot state when it matters most is not carried as data in any useful
    sense.
    """
    df = query("""select distinct training_week_floor from srv_edge_finder
                  where training_week_floor is not null limit 5""")
    return int(df["training_week_floor"].min()) if not df.empty else 5


@st.cache_data(ttl=3600)
def _seasons() -> list:
    return query("select distinct season from srv_edge_finder order by season desc limit 200"
                 )["season"].tolist()


def body(page) -> None:
    with states.section("srv_edge_finder"):
        floor = _floor()
        seasons = _seasons()
        if not seasons:
            states.empty(
                "Model-versus-market edges would be here.",
                "No model has scored a game yet, so there is nothing to compare against "
                "the book.")
            return

        requested = params.get("season")
        season = requested if requested in seasons else seasons[0]
        chosen_market = params.get("market")
        market_label = BY_CODE.get(chosen_market, list(MARKETS)[0])

        with st.sidebar:
            season = st.selectbox("Season", seasons, index=seasons.index(season))
            market_label = st.selectbox("Market", list(MARKETS),
                                        index=list(MARKETS).index(market_label))
            models = query("""select distinct model_name from srv_edge_finder
                              where season = :season order by model_name limit 40""",
                           {"season": season})["model_name"].tolist()
            model_options = ["All models"] + models
            chosen_model = params.get("model")
            model = st.selectbox(
                "Model", model_options,
                index=model_options.index(chosen_model)
                if chosen_model in model_options else 0)
            # The threshold is a filter on a value the view already computed, never a
            # recomputation of it. Its default is 0 so the page opens showing everything
            # rather than a pre-filtered subset a reader has to discover.
            minimum = st.slider("Minimum edge", 0.0, 25.0, 0.0, 0.5,
                                help="Absolute size, in the market's own unit.")

        market = MARKETS[market_label]
        model = None if model == "All models" else model
        params.set_params(season=season, market=market, model=model)

        df = query("""
            select game_id, season, season_type, week, model_name, model_family, split,
                   home_team, away_team, home_conference, away_conference,
                   market, edge_unit, edge_value, edge_magnitude, confidence_bucket,
                   spread, spread_home_perspective, predicted_margin,
                   predicted_margin_home_perspective,
                   predicted_home_win_probability, market_implied_home_win_probability,
                   actual_margin, actual_home_cover, cover_correct, home_win_correct,
                   is_out_of_sample_week, training_week_floor, is_default_actionable,
                   out_of_sample_note, model_version_key, attribution, as_of_ts
            from srv_edge_finder
            where season = :season
              and market = :market
              and (:model is null or model_name = :model)
              and edge_magnitude >= :minimum
            order by edge_magnitude desc
            limit 400
        """, {"season": season, "market": market, "model": model, "minimum": minimum})
        table.as_of_caption(df)

        if df.empty:
            _nothing_yet(season, floor, minimum, market_label)
            return

        _edges(df, market)
        attribution.model_attribution(df)


def _nothing_yet(season: int, floor: int, minimum: float, market_label: str) -> None:
    """Empty, never Degraded — and the reason must distinguish the two causes.

    "Too early in the season" and "your slider is set too high" are both zero-row answers
    with completely different fixes, and offering the wrong control is worse than offering
    none.
    """
    if minimum > 0:
        states.empty(
            f"Edges of {minimum:g} or more would be listed here.",
            f"No {market_label.lower()} edge that large exists in {season}.",
            fix_label="Reset the minimum to zero",
            fix=lambda: st.rerun())
        return
    states.empty(
        "Model-versus-market edges would be here.",
        f"Model predictions begin in Week {floor}. The {season} model needs several weeks "
        f"of current-season results before it can forecast this year's teams, so there is "
        f"nothing yet to compare against the book. This page will fill in as soon as the "
        f"first predictions land.")
    st.caption(
        "An edge is the model's number minus the market's. Both have to exist before the "
        "subtraction means anything — showing a placeholder here would imply the model has "
        "an opinion it does not have.")


def _bucket(row) -> str:
    """The pack writes an empty string where it has no bucket, and an empty cell reads as
    a value. Blank and absent are the same claim here, so both render as an em dash."""
    value = row.get("confidence_bucket")
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return fmt.EM_DASH
    return str(value)


def _result(row) -> str:
    """Whether the edge was right, once the game settled. Pending until it has."""
    correct = row.get("cover_correct") if row.get("market") == "spread" \
        else row.get("home_win_correct")
    if correct is None or (isinstance(correct, float) and pd.isna(correct)):
        return chips.chip_html("w", "Pending", "game not settled, or not graded")
    return chips.chip_html("y", "Hit") if bool(correct) else chips.chip_html("n", "Miss")


def _edges(df: pd.DataFrame, market: str) -> None:
    unit = df["edge_unit"].iloc[0] if "edge_unit" in df.columns and not df.empty else ""
    st.caption(f"Ranked by absolute edge, measured in {unit}. "
               f"Positive favours the home side.")
    columns = [
        Col("week", "Wk", "num", dp=0),
        Col("away_team", "Away"),
        Col("home_team", "Home"),
        Col("edge_value", "Edge", "signed"),
        Col("model_name", "Model"),
        Col("bucket", "Confidence", render=_bucket),
        Col("result", "Result", render=_result),
        Col("flag", "", render=lambda r: chips.out_of_sample_chip_html(
            bool(r.get("is_out_of_sample_week")))),
    ]
    # Labelled by what they ARE, not by whose they are. "Market" and "Model" alone
    # collided with the model-name column two places to the right, so the table carried two
    # columns headed Model and two headed Market — which the Excel export surfaced, because
    # a spreadsheet with duplicate headers is unusable in a way a web table merely looks
    # cluttered.
    if market == "spread":
        columns.insert(3, Col("spread_home_perspective", "Market spread", "signed"))
        columns.insert(4, Col("predicted_margin_home_perspective", "Model margin", "signed"))
    else:
        columns.insert(3, Col("market_implied_home_win_probability",
                              "Market win prob", "num"))
        columns.insert(4, Col("predicted_home_win_probability", "Model win prob", "num"))
    table.render(df, columns, caption="srv_edge_finder",
                 link_builder=lambda r: params.link("matchup", game_id=r["game_id"]))

    notes = df["out_of_sample_note"].dropna().unique()
    for note in notes:
        st.caption(str(note))


def render() -> None:
    shell.render_page("edges", body)
