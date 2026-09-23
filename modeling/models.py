"""Feature sets and models for Track 1 (the pack's features), cfdb-wtc-R-2420.

Everything a candidate model sees passes through `leakage.assert_no_leakage`. The one
exception is `reproduce_august_baseline`, which exists only to re-measure the model already
published in `srv_model_performance` — and that model was fed the closing spread. It is kept
apart, named for what it is, and never offered as a candidate.

FEATURE FORMS
    raw          the home_ and away_ columns as they come
    paired       each home/away pair turned into two numbers: a DIFFERENTIAL (away − home,
                 in the margin's own direction) and a SUM (away + home). A margin model reads
                 the differentials; a total model reads the sums; a team-points model reads
                 both. Half the columns per target, and each one points the way its target does.

FEATURE BREADTH
    notebook     the six pairs the pack's margin notebook uses: Elo, talent, adjusted EPA and
                 EPA allowed, adjusted success and success allowed
    wide         all 36 pairs the pack carries

Both breadths add `neutral_site` (home field is worth points, and a neutral site removes it).
`wide` also adds `week`.

TARGETS
    direct       one model for the margin, one for the total
    team_points  one model for each team's points; margin and total are then paired from them
"""
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from modeling.features import (AUGUST_BASELINE_FEATURES, NOTEBOOK_PAIRS, add_paired_columns,
                               august_baseline_frame, feature_sets, pairs_in)
from modeling.leakage import assert_no_leakage

RIDGE_ALPHA = 10.0          # the pack's own choice; fixed, not tuned on 2024
SEED = 2420


# ---------------------------------------------------------------- models

def make_model(family: str):
    if family == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
    if family == "hgb":
        # Fixed, conservative settings chosen before looking at 2024 — shallow trees, a
        # slow learning rate, and large leaves, because ~3,600 training games is small.
        return HistGradientBoostingRegressor(learning_rate=0.03, max_iter=400, max_leaf_nodes=8,
                                             min_samples_leaf=60, l2_regularization=1.0,
                                             random_state=SEED)
    raise ValueError(f"unknown model family {family!r}")


def _fit_predict(family: str, train: pd.DataFrame, target: pd.Series, cols: List[str],
                 score: pd.DataFrame) -> np.ndarray:
    if family == "avg":
        return (_fit_predict("ridge", train, target, cols, score)
                + _fit_predict("hgb", train, target, cols, score)) / 2
    model = make_model(family)
    model.fit(train[cols].astype(float), target)
    return model.predict(score[cols].astype(float))


def predict(train: pd.DataFrame, score: pd.DataFrame, form: str, breadth: str, family: str,
            target: str) -> Tuple[np.ndarray, np.ndarray]:
    """(predicted margin, predicted total) for `score`, from a model fitted on `train` only."""
    stems = list(NOTEBOOK_PAIRS) if breadth == "notebook" else pairs_in(train.columns)
    if form == "paired":
        train, score = add_paired_columns(train, stems), add_paired_columns(score, stems)
    sets = feature_sets(train.columns, form, breadth)

    if target == "direct":
        margin = _fit_predict(family, train, train["margin"], sets["margin"], score)
        total = _fit_predict(family, train, train["home_points"] + train["away_points"], sets["total"], score)
    elif target == "team_points":
        home = _fit_predict(family, train, train["home_points"], sets["points"], score)
        away = _fit_predict(family, train, train["away_points"], sets["points"], score)
        margin, total = away - home, away + home
    else:
        raise ValueError(f"unknown target {target!r}")
    return margin, total


# ---------------------------------------------------------------- the August baseline, re-measured

def reproduce_august_baseline(train: pd.DataFrame, score: pd.DataFrame, with_spread: bool = True) -> np.ndarray:
    """Re-measure `ridge_margin_expanded`: standardised ridge, alpha 10, on the notebook's inputs.

    🚨 WITH THE SPREAD. The published model took the closing line as an input, so reproducing
    it requires the line — which is why this function is NOT a candidate and does NOT pass
    through the leakage guard. `with_spread=False` gives the same model on the six football
    features alone: the honest baseline for a model that is never shown the line.
    """
    cols = list(AUGUST_BASELINE_FEATURES if with_spread else AUGUST_BASELINE_FEATURES[1:])
    if not with_spread:
        assert_no_leakage(cols)
    train, score = august_baseline_frame(train), august_baseline_frame(score)
    model = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
    model.fit(train[cols], train["margin"])
    return model.predict(score[cols])
