"""Feature sets for Track 1 — pure pandas, so the leakage checks on them run in CI.

FEATURE FORMS, BREADTHS and the August baseline's inputs are documented in `modeling.models`.
"""
from typing import Dict, Iterable, List

import pandas as pd

from modeling.leakage import assert_no_leakage, pack_feature_columns

NOTEBOOK_PAIRS = ("elo", "talent", "adjusted_epa", "adjusted_epa_allowed",
                  "adjusted_success", "adjusted_success_allowed")


def pairs_in(columns: Iterable[str]) -> List[str]:
    """Stems that appear as both home_<stem> and away_<stem> among guarded features."""
    features = pack_feature_columns(columns)
    homes = {c[len("home_"):] for c in features if c.startswith("home_")}
    aways = {c[len("away_"):] for c in features if c.startswith("away_")}
    return sorted(homes & aways)


def add_paired_columns(frame: pd.DataFrame, stems: Iterable[str]) -> pd.DataFrame:
    """Add <stem>_diff = away − home and <stem>_sum = away + home for every stem."""
    out = frame.copy()
    for stem in stems:
        out[f"{stem}_diff"] = out[f"away_{stem}"] - out[f"home_{stem}"]
        out[f"{stem}_sum"] = out[f"away_{stem}"] + out[f"home_{stem}"]
    return out


def feature_sets(columns: Iterable[str], form: str, breadth: str) -> Dict[str, List[str]]:
    """{'margin', 'total', 'points'} → the guarded feature list each model reads."""
    columns = list(columns)
    stems = list(NOTEBOOK_PAIRS) if breadth == "notebook" else pairs_in(columns)
    extra = ["neutral_site"] + (["week"] if breadth == "wide" else [])
    if form == "raw":
        raw = [f"{side}_{s}" for s in stems for side in ("home", "away")] + extra
        sets = {"margin": raw, "total": raw, "points": raw}
    elif form == "paired":
        diffs, sums = [f"{s}_diff" for s in stems], [f"{s}_sum" for s in stems]
        sets = {"margin": diffs + extra, "total": sums + extra, "points": diffs + sums + extra}
    else:
        raise ValueError(f"unknown feature form {form!r}")
    return {target: assert_no_leakage(cols) for target, cols in sets.items()}


# ---------------------------------------------------------------- the August baseline's inputs

AUGUST_BASELINE_FEATURES = ("spread", "elo_diff", "talent_diff", "epa_diff", "epa_allowed_diff",
                            "success_diff", "success_allowed_diff")


def august_baseline_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """The pack margin notebook's inputs, rebuilt: the spread plus six away − home differences."""
    out = frame.copy()
    for name, stem in (("elo", "elo"), ("talent", "talent"), ("epa", "adjusted_epa"),
                       ("epa_allowed", "adjusted_epa_allowed"), ("success", "adjusted_success"),
                       ("success_allowed", "adjusted_success_allowed")):
        out[f"{name}_diff"] = out[f"away_{stem}"] - out[f"home_{stem}"]
    return out
