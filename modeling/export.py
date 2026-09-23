"""Write predictions in the 42-column export contract (`src/load_predictions.CONTRACT_COLUMNS`).

Files go to `model_outputs/` at the checkout root, which is gitignored and refused by the
pre-commit hook: predictions on the pack's rows are derived from licensed data. Filenames are
our own and are never one of `load_predictions.EXPECTED_FILES`, so nothing here is picked up
by the warehouse loader by accident.

Margin/score models fill the margin, winner, cover and error fields; the probability, Brier and
log-loss fields stay blank, as the schema says unsupported fields must.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from modeling.data import REPO_ROOT
from src.load_predictions import CONTRACT_COLUMNS, EXPECTED_FILES

OUTPUT_DIR = REPO_ROOT / "model_outputs"


def export_frame(games: pd.DataFrame, pred_margin, pred_total, split: str, model_name: str,
                 model_family: str, target: str) -> pd.DataFrame:
    """One row per game in contract column order. Sign convention: margin = away − home."""
    g = games.reset_index(drop=True)
    margin = np.asarray(pred_margin, dtype=float)
    total = np.asarray(pred_total, dtype=float)
    out = pd.DataFrame({
        "game_id": g["id"], "season": g["season"], "season_type": g["season_type"], "week": g["week"],
        "start_date": g["start_date"], "neutral_site": g["neutral_site"],
        "home_team": g["home_team"], "away_team": g["away_team"],
        "home_conference": g["home_conference"], "away_conference": g["away_conference"],
        "split": split, "model_name": model_name, "model_family": model_family, "target": target,
        "home_points": g["home_points"], "away_points": g["away_points"],
    })
    out["actual_margin"] = g["away_points"] - g["home_points"]
    out["actual_total_points"] = g["away_points"] + g["home_points"]
    out["actual_home_win"] = g["home_points"] > g["away_points"]
    out["actual_winner"] = np.where(out["actual_home_win"], g["home_team"], g["away_team"])
    out["spread"] = g["spread"]
    out["actual_home_cover"] = _cover(out["actual_margin"], g["spread"])

    out["predicted_home_points"] = (total - margin) / 2
    out["predicted_away_points"] = (total + margin) / 2
    out["predicted_margin"] = margin
    out["predicted_total_points"] = total
    out["predicted_home_win"] = margin < 0
    out["predicted_winner"] = np.where(out["predicted_home_win"], g["home_team"], g["away_team"])
    out["predicted_home_cover"] = _cover(pd.Series(margin), g["spread"])
    out["home_cover_edge"] = g["spread"] - margin
    out["margin_error"] = margin - out["actual_margin"]
    out["absolute_margin_error"] = out["margin_error"].abs()
    out["home_win_correct"] = out["predicted_home_win"] == out["actual_home_win"]
    both = out["predicted_home_cover"].notna() & out["actual_home_cover"].notna()
    out["cover_correct"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[both, "cover_correct"] = out.loc[both, "predicted_home_cover"] == out.loc[both, "actual_home_cover"]

    for column in CONTRACT_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[list(CONTRACT_COLUMNS)]


def _cover(margin: pd.Series, spread: pd.Series) -> pd.Series:
    """True = home covers (margin below the line), False = away, blank = exactly on it."""
    result = pd.Series(pd.NA, index=margin.index, dtype="object")
    result[margin < spread] = True
    result[margin > spread] = False
    return result


def write_export(frame: pd.DataFrame, filename: str, directory: Path = OUTPUT_DIR) -> Path:
    if filename in EXPECTED_FILES:
        raise ValueError(f"{filename} is a filename the warehouse loader ingests; use a new one")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    frame.to_csv(path, index=False)
    return path
