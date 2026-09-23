"""Part 2 of cfdb-wtc-R-2420: every experiment scored on the 2024 validation season ONLY.

`validation_grid` is handed the train and validate frames and nothing else, so the test season
cannot be looked at from here by construction. Choosing is by margin MAE (and total MAE for
totals), never by ATS, which moves several points on luck alone over one season.
"""
from itertools import product

import pandas as pd

from modeling.evaluate import evaluate, rate_interval
from modeling.models import predict

FORMS = ("raw", "paired")
BREADTHS = ("notebook", "wide")
FAMILIES = ("ridge", "hgb", "avg")
TARGETS = ("direct", "team_points")


def score_row(name: str, frame: pd.DataFrame, pred_margin=None, pred_total=None, **labels) -> dict:
    """One results-table row: the model's four numbers and the ATS interval."""
    e = evaluate(frame, pred_margin=pred_margin, pred_total=pred_total)
    col = "model" if pred_margin is not None else "market"
    ats, ats_n = e.loc["ATS %", col], int(e.loc["ATS %", "games"])
    lo, hi = rate_interval(ats, ats_n) if pred_margin is not None else (float("nan"), float("nan"))
    return {"experiment": name, **labels,
            "margin_mae": e.loc["margin MAE (points)", col],
            "total_mae": e.loc["total MAE (points)", col],
            "straight_up": e.loc["straight-up %", col],
            "ats": ats, "ats_lo": lo, "ats_hi": hi, "ats_games": ats_n, "games": len(frame)}


def validation_grid(train: pd.DataFrame, validate: pd.DataFrame) -> pd.DataFrame:
    """The market's row first, then all 24 form × breadth × family × target combinations."""
    assert set(validate["season"]) == {2024}, "the grid is chosen on 2024 only"
    rows = [score_row("market (closing line)", validate)]
    for form, breadth, family, target in product(FORMS, BREADTHS, FAMILIES, TARGETS):
        margin, total = predict(train, validate, form, breadth, family, target)
        rows.append(score_row(f"{form}/{breadth}/{family}/{target}", validate, margin, total,
                              form=form, breadth=breadth, family=family, target=target))
    return pd.DataFrame(rows)
