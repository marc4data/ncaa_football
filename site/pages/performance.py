"""Model Performance — page 13.

This page exists to measure, not to flatter. Its headline is currently that the best model
does not beat the market, and it says so.

Four sections now that srv_model_performance carries segments: the headline table, then
by-week, by-conference and calibration. Calibration is the one that answers a question no
accuracy figure can — whether a 70% is worth 70 cents — and it is the section most likely
to be flattering, so it renders the model's own numbers against the realised rate with no
commentary smoothing the gap.
"""
import pandas as pd
import streamlit as st

from lib import attribution, chips, fmt, shell, states, table
from lib.query import query
from lib.table import Col

BREAKEVEN = 52.4          # ATS breakeven at −110.

# AC-13.4: the seventh model renders as a VISIBLE ROW MARKED NOT LOADED, never as a shorter
# table. fastai_wp_predictions.csv was never written, and a missing model is an absence the
# page states rather than an omission the reader has to notice.
EXPECTED_MODELS = {
    "ridge_margin_expanded", "random_forest_score", "xgboost_home_win_calibrated",
    "logistic_home_win_c_0.25", "xgboost_home_win_shap_explained",
    "stacked_ensemble_home_win", "fastai_home_win",
}

MEASURES = """
    model_name, model_version, model_family, split, season, is_out_of_sample_week,
    segment_type, segment_value, segment_order, games,
    mean_absolute_margin_error, mean_margin_error, brier_score, log_loss,
    winner_correct, winner_scored, winner_accuracy_pct,
    cover_correct_count, cover_scored, ats_accuracy_pct,
    mean_predicted_home_win_probability, actual_home_win_rate,
    attribution, as_of_ts
"""


def _ats(row) -> str:
    """AC-13.3: below breakeven renders in the negative treatment. No softening.

    AC-G.33: the rate carries its own n, and that n is `cover_scored` — NOT `games`. Those
    differ: pushes are blank in the prediction contract and excluded from cover accuracy, so
    a model with 567 games can have 553 graded covers. Showing the rate against the game
    count overstates the sample by exactly the number of pushes, which is small, systematic,
    and the kind of error nobody catches because both numbers look right.
    """
    value = row.get("ats_accuracy_pct")
    scored = row.get("cover_scored")
    if value is None or pd.isna(value):
        # Distinguish "no cover was graded" from "we have not measured this". Four of the
        # six models produce no cover prediction at all, and a bare em dash would read as
        # a gap in the data rather than a property of the model.
        if scored is not None and not pd.isna(scored) and int(scored) == 0:
            return chips.chip_html("w", fmt.EM_DASH,
                                   "this model produces no cover prediction, so no game "
                                   "has an against-the-spread result to grade")
        return fmt.EM_DASH
    variant = "y" if float(value) >= BREAKEVEN else "n"
    return chips.chip_html(variant, f"{float(value):.1f}% (n={int(scored):,})",
                           f"breakeven at −110 is {BREAKEVEN}%")


def _winner(row) -> str:
    """Straight-up accuracy, with the denominator that produced it."""
    value = row.get("winner_accuracy_pct")
    if value is None or pd.isna(value):
        return fmt.EM_DASH
    return f"{float(value):.1f}% (n={int(row.get('winner_scored') or 0):,})"


def body(page) -> None:
    with states.section("srv_model_performance"):
        # Filtered to 'overall'. The view now stacks five cuts, and an unfiltered read
        # would put week rows and conference rows in the headline table at incompatible
        # grains — numbers that all look like model accuracy and are not comparable.
        df = query(f"""
            select {MEASURES}
            from srv_model_performance
            where segment_type = 'overall'
            order by winner_accuracy_pct desc nulls last
            limit 200
        """)
        table.as_of_caption(df)

        # AC-12.6 / AC-13.5: a persistent, visible statement — not a tooltip, not a
        # footnote. Every figure here is a held-out backtest, and a backtest hit rate and a
        # realised hit rate must never render in identical styling.
        st.warning(
            "**Every figure on this page is a 2025 held-out backtest, not live betting.** "
            "The models were trained on seasons up to 2023 and validated on 2024; nothing "
            "here has been bet. A backtest number and a realised number are different "
            "claims.")

        if df.empty:
            states.empty("Model accuracy would be here.",
                         "No predictions have been loaded yet.")
            return

        columns = [
            Col("model_name", "Model"),
            Col("split", "Split"),
            Col("season", "Season", "num", dp=0),
            Col("games", "n", "num", dp=0),
            Col("mean_absolute_margin_error", "Margin MAE", "num"),
            Col("winner", "SU", render=_winner),
            Col("ats", "ATS", render=_ats),
            Col("brier_score", "Brier", "num"),
        ]
        table.render(df, columns, caption="srv_model_performance")

        _missing_models(df)

        # AC-13.6: the comparison is directional, and that is stated on the page rather
        # than only in a document.
        st.caption(
            "Comparison against the prior model (MAE 14.13, SU 70.0%, ATS 49.4% over 2025 "
            "weeks 5–8) is **directional rather than like-for-like** — different model, "
            "different sample window.")
        attribution.model_attribution(df)

        _breakdowns(sorted(df["model_name"].unique()))


def _missing_models(df: pd.DataFrame) -> None:
    loaded = set(df["model_name"].unique())
    missing = sorted(m for m in EXPECTED_MODELS if m not in loaded)
    if not missing:
        return
    for name in missing:
        st.markdown(
            f"<div class='cfdb-state cfdb-degraded'>"
            f"<div class='cfdb-state-title'>{name} — not loaded</div>"
            f"<div class='cfdb-state-body'>This model's export was never written, so it has "
            f"no rows. It is listed rather than omitted: a shorter table would hide the "
            f"absence.</div>"
            f"<div class='cfdb-state-object'>Waiting on "
            f"<code>fastai_wp_predictions.csv</code></div></div>",
            unsafe_allow_html=True)


def _segment(model: str, segment_type: str) -> pd.DataFrame:
    return query(f"""
        select {MEASURES}
        from srv_model_performance
        where segment_type = :segment_type and model_name = :model
        order by segment_order, segment_value
        limit 200
    """, {"segment_type": segment_type, "model": model})


def _breakdowns(models: list) -> None:
    st.divider()
    st.subheader("Breakdowns")
    model = st.selectbox("Model", models,
                         help="Breakdowns are per model; averaging across models would "
                              "produce a figure no model achieved.")
    tabs = st.tabs(["By week", "By conference", "Calibration", "By confidence"])

    with tabs[0]:
        states.render_or_state(
            _segment(model, "week"), "srv_model_performance",
            "Week-by-week accuracy would be here.",
            "This model has no per-week rows.",
            renderer=lambda d: _segment_table(d, "Week"))

    with tabs[1]:
        df = _segment(model, "conference")
        # A game has two conferences and is counted under both, so these deliberately sum
        # to more than the overall row. Saying so is cheaper than a reader adding them up
        # and concluding the page is broken.
        st.caption(
            "A game counts under both teams' conferences, so these add up to more than the "
            "total above. 'How does the model do on SEC games' includes a visitor's trip "
            "to an SEC stadium.")
        states.render_or_state(
            df, "srv_model_performance",
            "Conference breakdowns would be here.",
            "This model has no per-conference rows.",
            renderer=lambda d: _segment_table(d, "Conference"))

    with tabs[2]:
        _calibration(model)

    with tabs[3]:
        st.caption(
            "The model's own confidence label against what it actually achieved. A label "
            "that does not separate the outcomes is a label worth ignoring.")
        states.render_or_state(
            _segment(model, "confidence"), "srv_model_performance",
            "Confidence buckets would be here.",
            "This model publishes no confidence bucket.",
            renderer=lambda d: _segment_table(d, "Confidence"))


def _segment_table(df: pd.DataFrame, label: str) -> None:
    table.render(df, [
        Col("segment_value", label),
        Col("games", "n", "num", dp=0),
        Col("mean_absolute_margin_error", "Margin MAE", "num"),
        Col("winner", "SU", render=_winner),
        Col("ats", "ATS", render=_ats),
        Col("brier_score", "Brier", "num"),
    ], caption="srv_model_performance", max_rows=100)


def _calibration(model: str) -> None:
    """Predicted probability against realised rate. The question accuracy cannot answer.

    A model can be 73% accurate and badly calibrated — confident when it should not be — and
    only this comparison shows it. Both columns come from the view; the page draws them and
    computes nothing.
    """
    df = _segment(model, "probability")
    if df.empty:
        states.empty(
            "A calibration curve would be here.",
            "This model publishes no win probability, so there is nothing to calibrate. "
            "A margin model predicts a number of points, not a likelihood.")
        return

    st.caption(
        "A perfectly calibrated model has the two columns equal in every bucket: of the "
        "games it called 70%, 70% should have been won. A gap is the size and direction of "
        "its over- or under-confidence.")
    chart = df.set_index("segment_value")[
        ["mean_predicted_home_win_probability", "actual_home_win_rate"]].astype(float)
    chart.columns = ["Model says", "Actually happened"]
    st.line_chart(chart, height=260)

    table.render(df, [
        Col("segment_value", "Predicted band"),
        Col("games", "n", "num", dp=0),
        Col("mean_predicted_home_win_probability", "Model says", "num"),
        Col("actual_home_win_rate", "Actually happened", "num"),
        Col("brier_score", "Brier", "num"),
    ], caption="srv_model_performance", max_rows=20)
    # AC-G.33 applies hardest here: a bucket holding one game is not evidence of anything,
    # and a calibration chart makes every point look equally weighted.
    thin = df[df["games"] < 20]
    if not thin.empty:
        st.caption(
            f"{len(thin)} band(s) hold fewer than 20 games — "
            f"{', '.join(thin['segment_value'])}. A point on this chart is only as good as "
            f"its n, and the chart does not show that.")


def render() -> None:
    shell.render_page("performance", body)
