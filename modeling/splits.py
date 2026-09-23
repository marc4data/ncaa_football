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


def split(frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """{'train', 'validate', 'test'} — regular season, disjoint by season."""
    regular = regular_season(frame)
    return {
        "train": regular[regular["season"] <= TRAIN_LAST_SEASON],
        "validate": regular[regular["season"] == VALIDATE_SEASON],
        "test": regular[regular["season"] == TEST_SEASON],
    }
