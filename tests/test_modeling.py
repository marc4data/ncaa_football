"""The modeling workspace: data contract, splits, the leakage guard, and the evaluator.

Almost everything here runs on SYNTHETIC frames, so it runs in CI, where the licensed pack is
absent by design. One test reads the real pack and skips with its reason when it is not on
the machine; it pins the evaluator to numbers the pack's own leaderboard published.

Column names below are generic football names chosen for the test, not the pack's header.
"""
import numpy as np
import pandas as pd
import pytest

from modeling import data, leakage, splits
from modeling.evaluate import ATS_BREAK_EVEN, evaluate


def _frame(rows):
    """A frame shaped like the pack, from (season, season_type, home_pts, away_pts, spread)."""
    out = pd.DataFrame(rows, columns=["season", "season_type", "home_points", "away_points", "spread"])
    out["id"] = range(1, len(out) + 1)
    out["week"] = 6
    out["home_team"], out["away_team"] = "Home U", "Away State"
    out["margin"] = out["away_points"] - out["home_points"]
    return out


@pytest.fixture
def small_frame():
    return _frame([
        (2022, "regular", 30, 20, -7.0),
        (2023, "regular", 14, 21, 3.0),
        (2024, "regular", 27, 24, -3.0),
        (2025, "regular", 10, 35, 10.0),
        (2025, "postseason", 21, 17, -1.5),
    ])


# ---------------------------------------------------------------- the data contract

def test_contract_passes_a_well_formed_frame(small_frame):
    data.check_contract(small_frame, expected_rows=len(small_frame))


def test_contract_refuses_a_flipped_margin(small_frame):
    small_frame.loc[0, "margin"] = -small_frame.loc[0, "margin"]
    with pytest.raises(data.ContractError, match="margin != away_points - home_points"):
        data.check_contract(small_frame, expected_rows=len(small_frame))


def test_contract_refuses_season_2020(small_frame):
    small_frame.loc[0, "season"] = 2020
    with pytest.raises(data.ContractError, match="season 2020"):
        data.check_contract(small_frame, expected_rows=len(small_frame))


def test_contract_refuses_the_wrong_row_count(small_frame):
    with pytest.raises(data.ContractError, match="expected 5,133 rows, found 5"):
        data.check_contract(small_frame)


def test_missing_pack_says_how_to_point_at_it(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "REPO_ROOT", tmp_path)
    monkeypatch.setenv(data.PACK_ENV, str(tmp_path / "nowhere"))
    with pytest.raises(data.PackNotFound) as raised:
        data.pack_dir()
    assert data.PACK_ENV in str(raised.value)
    assert "must never be committed" in str(raised.value)


def test_pack_env_var_wins(tmp_path, monkeypatch):
    (tmp_path / data.TRAINING_FILE).write_text("id\n")
    monkeypatch.setenv(data.PACK_ENV, str(tmp_path))
    assert data.pack_dir() == tmp_path


# ---------------------------------------------------------------- splits

def test_splits_are_by_season_and_regular_season_only(small_frame):
    parts = splits.split(small_frame)
    assert parts["train"]["season"].tolist() == [2022, 2023]
    assert parts["validate"]["season"].tolist() == [2024]
    assert parts["test"]["season"].tolist() == [2025]
    assert all((p["season_type"] == "regular").all() for p in parts.values())


# ---------------------------------------------------------------- the leakage guard

@pytest.mark.parametrize("outcome", ["home_points", "away_points", "margin", "spread"])
def test_guard_refuses_every_outcome_and_the_line(outcome):
    with pytest.raises(leakage.LeakageError, match=outcome):
        leakage.assert_no_leakage(["home_elo", outcome])


@pytest.mark.parametrize("derived", ["home_win", "total_points", "ats_cover", "final_score", "spread_edge"])
def test_guard_refuses_columns_derived_from_the_outcome(derived):
    assert leakage.leaking_columns(["home_elo", derived]) == [derived]


@pytest.mark.parametrize("feature", ["home_total_havoc_offense", "home_points_per_opportunity_offense",
                                     "away_stats_rank", "home_elo"])
def test_guard_lets_real_pregame_features_through(feature):
    assert leakage.assert_no_leakage([feature]) == [feature]


def test_guard_takes_extra_names_it_cannot_see():
    assert leakage.leaking_columns(["home_final_diff"]) == []          # invisible to the patterns
    with pytest.raises(leakage.LeakageError, match="home_final_diff"):
        leakage.assert_no_leakage(["home_elo", "home_final_diff"], also_forbid=["home_final_diff"])


def test_pack_feature_list_passes_the_leakage_guard():
    """The list the builder offers a model contains no outcome and no line.

    STAGED BREAK (cfdb-wtc-R-2413): dropping "spread" from `leakage.NOT_FEATURES` puts the
    closing line in the feature list, and THIS test goes red with LeakageError.
    """
    columns = ["id", "start_date", "season", "season_type", "week", "neutral_site",
               "home_team", "away_team", "home_conference", "away_conference",
               "home_elo", "away_elo", "home_total_havoc_offense", "home_points_per_opportunity_offense",
               "home_points", "away_points", "margin", "spread"]
    features = leakage.pack_feature_columns(columns)
    assert features == ["week", "neutral_site", "home_elo", "away_elo",
                        "home_total_havoc_offense", "home_points_per_opportunity_offense"]


# ---------------------------------------------------------------- the evaluator

def test_market_baseline_on_known_rows():
    frame = _frame([
        (2025, "regular", 30, 20, -7.0),   # margin -10: market picked home, home won; |−10 − −7| = 3
        (2025, "regular", 14, 21, 3.0),    # margin +7:  market picked away, away won; |7 − 3| = 4
        (2025, "regular", 27, 24, 3.0),    # margin −3:  market picked away, HOME won; |−3 − 3| = 6
        (2025, "regular", 20, 23, 3.0),    # margin +3:  PUSH against the line; |3 − 3| = 0
    ])
    result = evaluate(frame)
    assert result.loc["margin MAE (points)", "market"] == pytest.approx((3 + 4 + 6 + 0) / 4)
    assert result.loc["straight-up %", "market"] == pytest.approx(3 / 4)
    assert result.loc["ATS %", "market"] == pytest.approx(ATS_BREAK_EVEN)
    assert result.loc["ATS %", "games"] == 3
    assert "pushes excluded: 1" in result.loc["ATS %", "note"]


def test_model_ats_excludes_and_counts_pushes_and_no_bets():
    frame = _frame([
        (2025, "regular", 30, 20, -7.0),   # actual −10, line −7: home covered
        (2025, "regular", 14, 21, 3.0),    # actual +7,  line +3: away covered
        (2025, "regular", 20, 23, 3.0),    # actual +3,  line +3: PUSH
        (2025, "regular", 17, 10, 1.0),    # actual −7,  line +1: home covered
    ])
    pred = [-12.0, 1.0, 9.0, 1.0]          # backs home (win) · home (loss) · away (push) · ON THE LINE
    result = evaluate(frame, pred_margin=pred, pred_total=[50, 35, 43, 27])
    assert result.loc["ATS %", "model"] == pytest.approx(1 / 2)
    assert result.loc["ATS %", "games"] == 2
    assert "pushes excluded: 1" in result.loc["ATS %", "note"]
    assert "on-the-line (no bet): 1" in result.loc["ATS %", "note"]
    assert result.loc["margin MAE (points)", "model"] == pytest.approx((2 + 6 + 6 + 8) / 4)
    assert result.loc["straight-up %", "model"] == pytest.approx(3 / 4)   # row 4 picks away; home won
    assert result.loc["total MAE (points)", "model"] == pytest.approx((0 + 0 + 0 + 0) / 4)
    assert np.isnan(result.loc["total MAE (points)", "market"])


# ---------------------------------------------------------------- the real pack, when present

def test_real_pack_contract_and_2025_matches_the_packs_leaderboard():
    """The pack's own leaderboard (08_…ipynb, saved outputs) scores 567 regular-season 2025
    games, 553 of them decided against the spread and 14 pushes. A push depends only on the
    rows, not the model, so our evaluator must reproduce all three."""
    try:
        frame = data.load_pack()
    except data.PackNotFound as missing:
        pytest.skip(f"licensed pack not on this machine: {str(missing).splitlines()[0]}")
    test = splits.split(frame)["test"]
    result = evaluate(test)
    assert len(test) == 567
    assert result.loc["ATS %", "games"] == 553
    assert "pushes excluded: 14" in result.loc["ATS %", "note"]
