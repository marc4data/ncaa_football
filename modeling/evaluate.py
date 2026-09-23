"""Score predictions the way the site will be judged: beside the market, on the same games.

Every number here is reported next to the market's number on the SAME rows, because a model
MAE means nothing on its own — "off by 12 points" is excellent in a season of blowouts and
poor in a season of close games. The market is the bar.

The market's predictions are read straight off the closing line, in the pack's convention:

    predicted margin (away - home) = spread
    e.g. spread -7  →  home favoured by 7  →  market expects margin -7

THE METRICS, and what each one excludes and counts rather than hides:

    margin MAE     mean |predicted margin - actual margin|, in points
    total MAE      mean |predicted total - actual total| — model only: the pack carries no
                   closing total, so there is no market total to stand beside it
    straight-up    % of games where the predicted winner won. A prediction of exactly 0 (or a
                   pick'em line) names no winner: excluded, and counted in `no_pick`
    ATS            against the spread: we back the side our margin is on relative to the line.
                   A PUSH (final margin exactly equals the spread) is excluded and counted.
                   A prediction exactly ON the line backs nobody: excluded, counted in `no_bet`.
                   The market has no ATS number — it IS the line — so its column reads the
                   -110 break-even, 52.4%, which is what a model has to beat to make money.
"""
from typing import Optional

import numpy as np
import pandas as pd

ATS_BREAK_EVEN = 110 / 210  # 52.38%: win 100 for every 110 risked


def _straight_up(pred_margin: pd.Series, actual_margin: pd.Series) -> dict:
    picked = np.sign(pred_margin)
    has_pick = picked != 0
    correct = (picked == np.sign(actual_margin)) & has_pick
    n = int(has_pick.sum())
    return {"pct": correct.sum() / n if n else np.nan, "n": n, "no_pick": int((~has_pick).sum())}


def _against_the_spread(pred_margin: pd.Series, actual_margin: pd.Series, spread: pd.Series) -> dict:
    side = np.sign(pred_margin - spread)          # +1 backs away to cover, -1 backs home
    result = np.sign(actual_margin - spread)      # +1 away covered, -1 home covered, 0 push
    push = result == 0
    no_bet = side == 0
    decided = ~push & ~no_bet
    wins = int(((side == result) & decided).sum())
    n = int(decided.sum())
    return {"pct": wins / n if n else np.nan, "n": n, "wins": wins,
            "pushes": int(push.sum()), "no_bet": int((no_bet & ~push).sum())}


def evaluate(frame: pd.DataFrame, pred_margin: Optional[pd.Series] = None,
             pred_total: Optional[pd.Series] = None) -> pd.DataFrame:
    """One row per metric: the model's number, the market's, and the counts behind them.

    `frame` needs `margin`, `spread`, `home_points`, `away_points`. With no predictions it
    returns the market's own numbers, which is how the market baseline is reported.
    """
    actual = frame["margin"]
    spread = frame["spread"]
    market_su = _straight_up(spread, actual)
    push_count = int((actual == spread).sum())

    rows = [{
        "metric": "margin MAE (points)", "model": np.nan,
        "market": float((actual - spread).abs().mean()), "games": len(frame), "note": "",
    }, {
        "metric": "straight-up %", "model": np.nan, "market": market_su["pct"],
        "games": market_su["n"], "note": f"market pick'em lines excluded: {market_su['no_pick']}",
    }, {
        "metric": "ATS %", "model": np.nan, "market": ATS_BREAK_EVEN,
        "games": len(frame) - push_count,
        "note": f"pushes excluded: {push_count}; market column is the -110 break-even",
    }, {
        "metric": "total MAE (points)", "model": np.nan, "market": np.nan, "games": len(frame),
        "note": "no closing total in the pack, so no market figure",
    }]

    if pred_margin is not None:
        pred_margin = pd.Series(np.asarray(pred_margin, dtype=float), index=frame.index)
        su = _straight_up(pred_margin, actual)
        ats = _against_the_spread(pred_margin, actual, spread)
        rows[0]["model"] = float((actual - pred_margin).abs().mean())
        rows[1]["model"] = su["pct"]
        rows[1]["note"] += f"; model no-pick: {su['no_pick']}"
        rows[2]["model"] = ats["pct"]
        rows[2]["games"] = ats["n"]
        rows[2]["note"] = (f"pushes excluded: {ats['pushes']}; on-the-line (no bet): {ats['no_bet']}; "
                           "market column is the -110 break-even")

    if pred_total is not None:
        actual_total = frame["home_points"] + frame["away_points"]
        pred_total = pd.Series(np.asarray(pred_total, dtype=float), index=frame.index)
        rows[3]["model"] = float((actual_total - pred_total).abs().mean())

    return pd.DataFrame(rows).set_index("metric")


def market_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    """The market's own margin MAE and straight-up rate on these rows — the bar to clear."""
    return evaluate(frame)[["market", "games", "note"]]


def rate_interval(rate: float, n: int, z: float = 1.96) -> tuple:
    """A 95% range for a hit rate measured on n games (normal approximation).

    ATS on ~550 games carries a range of about ±4 points: 51% and 53% are not distinguishable
    on one season, and this is the number that says so.
    """
    if not n or rate != rate:
        return (np.nan, np.nan)
    half = z * np.sqrt(rate * (1 - rate) / n)
    return (rate - half, rate + half)
