"""Model Performance — page 13.

This page exists to measure, not to flatter. Its headline is currently that the best model
does not beat the market, and it says so.
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


def _ats(row) -> str:
    """AC-13.3: below breakeven renders in the negative treatment. No softening."""
    value = row.get("ats_accuracy_pct")
    if value is None or pd.isna(value):
        return fmt.EM_DASH
    variant = "y" if float(value) >= BREAKEVEN else "n"
    return chips.chip_html(variant, f"{float(value):.1f}%",
                           f"breakeven at −110 is {BREAKEVEN}%")


def body(page) -> None:
    with states.section("srv_model_performance"):
        df = query("""
            select model_name, model_version, model_family, split, season,
                   is_out_of_sample_week, games, mean_absolute_margin_error,
                   winner_accuracy_pct, ats_accuracy_pct, brier_score, log_loss,
                   winner_scored, cover_scored, attribution, as_of_ts
            from srv_model_performance
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
            Col("winner_accuracy_pct", "SU %", "num"),
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


def render() -> None:
    shell.render_page("performance", body)
