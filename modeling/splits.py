"""Train, validate and test — by season, never by shuffling rows.

A random split would put a Week 9 game in training and the Week 8 game before it in testing,
and the model would be graded on the past with knowledge of the future. Splitting by season
keeps every test game strictly after everything the model learned from.

    train     2016-2019, 2021-2023   (2020 is absent from the pack)
    validate  2024                   choose between candidates here
    test      2025                   score each candidate set here ONCE

Regular season only, per the modeling spec §5.
"""
from typing import Dict

import pandas as pd

TRAIN_LAST_SEASON = 2023
VALIDATE_SEASON = 2024
TEST_SEASON = 2025


def regular_season(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["season_type"] == "regular"]


class SplitError(ValueError):
    """A split holds a game from the wrong season — the test set has leaked into choosing."""


def check_splits(parts: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Refuse any split whose seasons are not exactly what the design says, or that share a game."""
    expected = {
        "train": lambda s: s <= TRAIN_LAST_SEASON,
        "validate": lambda s: s == VALIDATE_SEASON,
        "test": lambda s: s == TEST_SEASON,
    }
    problems = []
    for name, rule in expected.items():
        wrong = parts[name][~rule(parts[name]["season"])]
        if len(wrong):
            seasons = sorted(int(s) for s in wrong["season"].unique())
            problems.append(f"{name} holds {len(wrong)} game(s) from season(s) {seasons}")
    ids = [set(parts[n]["id"]) for n in expected]
    if ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2]:
        problems.append("a game appears in more than one split")
    if problems:
        raise SplitError("split refused:\n  - " + "\n  - ".join(problems))
    return parts


def split(frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """{'train', 'validate', 'test'} — regular season, disjoint by season, checked before return."""
    regular = regular_season(frame)
    return check_splits({
        "train": regular[regular["season"] <= TRAIN_LAST_SEASON],
        "validate": regular[regular["season"] == VALIDATE_SEASON],
        "test": regular[regular["season"] == TEST_SEASON],
    })
