"""Walk-forward tuning guards (cfdb-wtc-R-2490). A fake model stands in for the real one, so the
exam's walls are tested in CI without scikit-learn and without any data."""
import numpy as np
import pandas as pd
import pytest

from modeling import tune


def _frame():
    rows = []
    for season in range(2016, 2026):
        for g in range(4):
            rows.append({"id": season * 10 + g, "season": season, "week": 6, "margin": float(g), "spread": 0.0,
                         "market_total": np.nan, "home_points": 20.0, "away_points": 20.0 + g,
                         "home_elo_diff_x": 1.0, "away_elo_diff_x": 1.0})
    return pd.DataFrame(rows)


def _fake_predict(seen):
    def predict(train, test, *args, **kwargs):
        seen.append((sorted(train["season"].unique()), sorted(test["season"].unique())))
        return np.zeros(len(test)), np.full(len(test), 40.0)
    return predict


def test_walk_forward_trains_only_on_earlier_seasons():
    """STAGED BREAK (b), cfdb-wtc-R-2490: letting a fold season into its own training set
    (`fold_train_seasons` → `range(FIRST_TRAIN, test_season + 1)`) turns THIS test RED."""
    seen = []
    tune.walk_forward(_frame(), tune.Config(), _fake_predict(seen))
    assert [test for _, test in seen] == [[s] for s in tune.FOLDS]
    for train, (test,) in seen:
        assert max(train) < test and min(train) == tune.FIRST_TRAIN


def test_the_exam_season_is_refused_in_any_fold():
    """STAGED BREAK (a), cfdb-wtc-R-2490: dropping the exam clause from `check_fold`, so 2025 can be a
    fold, turns THIS test RED."""
    with pytest.raises(tune.FoldError, match="held-out exam"):
        tune.walk_forward(_frame(), tune.Config(), _fake_predict([]), folds=(2024, 2025))
    with pytest.raises(tune.FoldError, match="held-out exam"):
        tune.check_fold([2016, 2025], 2026)
    tune.check_fold(list(range(2016, 2025)), 2025, exam_open=True)      # the one pre-registered look


def test_a_fold_that_trains_on_itself_or_the_future_is_refused():
    with pytest.raises(tune.FoldError, match="its own season"):
        tune.check_fold([2019, 2020], 2020)
    with pytest.raises(tune.FoldError, match="later season"):
        tune.check_fold([2021], 2020)


def test_training_window_and_2020_exclusion():
    assert tune.fold_train_seasons(2024, tune.Config(train_window=3)) == [2021, 2022, 2023]
    assert 2020 not in tune.fold_train_seasons(2024, tune.Config(exclude_2020_from_training=True))


def test_a_gain_smaller_than_its_fold_error_is_no_gain():
    base = pd.DataFrame({"fold": [1, 2, 3, 4], "margin_mae": [12.0, 12.0, 12.0, 12.0]})
    noisy = pd.DataFrame({"fold": [1, 2, 3, 4], "margin_mae": [11.5, 12.5, 11.9, 12.0]})   # mean gain 0.025
    steady = pd.DataFrame({"fold": [1, 2, 3, 4], "margin_mae": [11.9, 11.9, 11.9, 11.9]})
    assert tune.gain(noisy, base)["verdict"] == "no gain"
    assert tune.gain(steady, base)["verdict"] == "gain"


def test_featureless_games_are_dropped_and_counted_never_imputed():
    f = _frame()
    f.loc[f["id"] == 20200, "home_elo_diff_x"] = np.nan
    result = tune.walk_forward(f, tune.Config(), _fake_predict([]))
    assert result.set_index("fold").loc[2020, "dropped_no_features"] == 1
    assert result.set_index("fold").loc[2020, "games"] == 3
