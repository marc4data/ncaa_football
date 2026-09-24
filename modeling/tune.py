"""Walk-forward tuning on ten seasons of our own features (cfdb-wtc-R-2491…R-2493).

THE EXAM. For each fold season S in 2018–2024: train on every own-feature season before S (from 2016),
score S (regular season, Week 5+). The selection metric is the MEAN MARGIN MAE ACROSS FOLDS; totals are
scored the same way, separately. A tweak's gain is measured fold by fold, and a gain smaller than its
fold standard error is reported as NO GAIN — seven folds are seven samples, not seven thousand.

2025 IS THE HELD-OUT EXAM. `check_fold` refuses it anywhere in Parts 1–4, and refuses a fold whose
own season sits in its training set. Both refusals are tested with a staged break.

THE MARKET, for evaluation only (never an input — the leakage guard stays on): the licensed pack's
closing `spread` for 2016–2025 (2020 absent), and the warehouse's lines for the 2024 total. No market
total exists before 2024.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

FOLDS = (2018, 2019, 2020, 2021, 2022, 2023, 2024)
EXAM = 2025
FIRST_TRAIN = 2016


class FoldError(ValueError):
    """A fold that would read the exam season, or train on the season it scores."""


def check_fold(train_seasons: Iterable[int], test_season: int, exam_open: bool = False) -> None:
    train_seasons = set(int(s) for s in train_seasons)
    if test_season in train_seasons:
        raise FoldError(f"fold {test_season} trains on its own season")
    if any(s >= test_season for s in train_seasons):
        later = sorted(s for s in train_seasons if s >= test_season)
        raise FoldError(f"fold {test_season} trains on a later season: {later}")
    if not exam_open and (test_season == EXAM or EXAM in train_seasons):
        raise FoldError(f"{EXAM} is the held-out exam; it is read once, after pre-registration")


@dataclass
class Config:
    """Everything a walk-forward run can vary. Feature-building knobs live with the frame, not here."""
    family: str = "ridge"
    ridge_alpha: float = 10.0
    hgb_params: Optional[dict] = None
    drop_families: tuple = ()
    train_window: Optional[int] = None            # None = every season from 2016
    exclude_2020_from_training: bool = False
    extra: Dict[str, object] = field(default_factory=dict)


FAMILY_TOKENS = {"field_position": "avg_start", "points_per_opportunity": "points_per_opportunity",
                 "havoc": "havoc", "explosiveness": "explosiveness"}


def drop_family_columns(frame: pd.DataFrame, families: Iterable[str]) -> pd.DataFrame:
    cols = [c for c in frame.columns if c.startswith(("home_", "away_"))
            and any(FAMILY_TOKENS[f] in c for f in families)]
    return frame.drop(columns=cols)


def fold_train_seasons(test_season: int, config: Config) -> List[int]:
    seasons = list(range(FIRST_TRAIN, test_season))
    if config.exclude_2020_from_training:
        seasons = [s for s in seasons if s != 2020]
    if config.train_window:
        seasons = seasons[-config.train_window:]
    return seasons


def walk_forward(frame: pd.DataFrame, config: Config, predict: Callable,
                 folds: Iterable[int] = FOLDS, score_ids: Optional[set] = None) -> pd.DataFrame:
    """`score_ids` scores only those games, so two configurations that can build features for
    different games (carry-forward fills 2020's first games) are compared on the SAME games."""
    """One row per fold: model and market margin MAE, model total MAE (and market where it exists)."""
    frame = drop_family_columns(frame, config.drop_families) if config.drop_families else frame
    # A game whose team has no earlier game this season has no in-season features (34 games of 2020,
    # when conferences started as late as Week 8). They are dropped and COUNTED, never imputed.
    feats = [c for c in frame.columns if c.startswith(("home_", "away_"))
             and c not in ("home_team", "away_team", "home_points", "away_points", "home_conference",
                           "away_conference")]
    usable = frame[feats].notna().all(axis=1)
    dropped = frame.loc[~usable].groupby("season").size()
    frame = frame[usable]
    rows = []
    for season in folds:
        train_seasons = fold_train_seasons(season, config)
        check_fold(train_seasons, season)
        train, test = frame[frame["season"].isin(train_seasons)], frame[frame["season"] == season]
        if score_ids is not None:
            test = test[test["id"].isin(score_ids)]
        margin, total = predict(train, test, "paired", "wide", config.family, "direct",
                                ridge_alpha=config.ridge_alpha, hgb_params=config.hgb_params)
        actual_total = (test["home_points"] + test["away_points"]).to_numpy()
        spread_ok = test["spread"].notna().to_numpy()
        total_ok = test["market_total"].notna().to_numpy()
        m_err = np.abs(test["margin"].to_numpy() - margin)
        t_err = np.abs(actual_total - total)
        rows.append({
            "fold": season, "train": f"{train_seasons[0]}–{train_seasons[-1]}", "games": len(test),
            "dropped_no_features": int(dropped.get(season, 0)),
            "train_dropped_no_features": int(sum(dropped.get(s, 0) for s in train_seasons)),
            "margin_mae": m_err.mean(), "total_mae": t_err.mean(),
            "games_with_line": int(spread_ok.sum()),
            "margin_mae_lined": m_err[spread_ok].mean() if spread_ok.any() else np.nan,
            "market_margin_mae": np.abs(test["margin"].to_numpy() - test["spread"].to_numpy())[spread_ok].mean()
            if spread_ok.any() else np.nan,
            "total_mae_vs_market_rows": t_err[total_ok].mean() if total_ok.any() else np.nan,
            "market_total_mae": np.abs(actual_total - test["market_total"].to_numpy())[total_ok].mean()
            if total_ok.any() else np.nan,
            "_m_err": m_err, "_t_err": t_err, "_ids": test["id"].to_numpy(),
        })
    return pd.DataFrame(rows)


def gain(candidate: pd.DataFrame, baseline: pd.DataFrame, metric: str = "margin_mae") -> dict:
    """Mean fold-level improvement (positive = better), its standard error, and the verdict."""
    d = baseline.set_index("fold")[metric] - candidate.set_index("fold")[metric]
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"gain": float(d.mean()), "se": float(se), "folds_better": int((d > 0).sum()), "folds": len(d),
            "verdict": "gain" if d.mean() > se else "no gain"}


def summary(result: pd.DataFrame) -> dict:
    return {"margin_mae": float(result["margin_mae"].mean()), "total_mae": float(result["total_mae"].mean())}
