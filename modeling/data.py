"""Load the training pack and check it is the file we think it is.

The pack is read from disk, never from the repository. Where it lives is resolved in this
order, and the first that exists wins:

    1. the CFDB_MODEL_PACK environment variable, if set
    2. `cfdb_model_pack/` at the root of this checkout (gitignored)

`check_contract()` runs before anything else touches the frame. A model trained on the wrong
file does not fail — it produces numbers — so the contract fails loudly instead.
"""
import os
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_ENV = "CFDB_MODEL_PACK"
PACK_DIRNAME = "cfdb_model_pack"
TRAINING_FILE = "training_data.csv"

# The contract, as measured on the 2026 Edition pack (cfdb-wtc-R-2410).
EXPECTED_ROWS = 5133
EXCLUDED_SEASON = 2020
REQUIRED_COLUMNS = (
    "id", "season", "season_type", "week", "home_team", "away_team",
    "home_points", "away_points", "margin", "spread",
)


class PackNotFound(FileNotFoundError):
    """The licensed pack is not on this machine, or not where we looked."""


class ContractError(ValueError):
    """The file loaded is not the training pack this code was written against."""


def pack_dir() -> Path:
    """Where the pack is, or a PackNotFound that says how to point at it."""
    candidates = []
    if os.environ.get(PACK_ENV):
        candidates.append(Path(os.environ[PACK_ENV]).expanduser())
    candidates.append(REPO_ROOT / PACK_DIRNAME)

    for path in candidates:
        if (path / TRAINING_FILE).is_file():
            return path

    looked = "\n".join(f"  - {p / TRAINING_FILE}" for p in candidates)
    raise PackNotFound(
        f"The CFB Model Training Pack was not found. Looked for:\n{looked}\n"
        f"Either unzip the pack into `{PACK_DIRNAME}/` at the root of this checkout (it is "
        f"gitignored), or set {PACK_ENV} to the folder that holds {TRAINING_FILE}. "
        "The pack is licensed and must never be committed."
    )


def load_pack(check: bool = True) -> pd.DataFrame:
    """The pack's training rows, contract-checked unless told otherwise."""
    frame = pd.read_csv(pack_dir() / TRAINING_FILE)
    if check:
        check_contract(frame)
    return frame


def check_contract(frame: pd.DataFrame, expected_rows: int = EXPECTED_ROWS) -> None:
    """Fail loudly unless the frame is the pack as we know it.

    Three facts, each checked on every row rather than sampled:
      - the row count is the one the pack ships with;
      - `margin == away_points - home_points` everywhere, which pins the sign convention;
      - season 2020 is absent, as the pack documents.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ContractError(f"columns missing from the training file: {missing}")

    problems = []
    if len(frame) != expected_rows:
        problems.append(f"expected {expected_rows:,} rows, found {len(frame):,}")

    wrong_margin = frame["margin"] != frame["away_points"] - frame["home_points"]
    if wrong_margin.any():
        example = frame.loc[wrong_margin, ["id", "home_points", "away_points", "margin"]].head(3)
        problems.append(
            f"margin != away_points - home_points on {int(wrong_margin.sum())} rows, e.g.\n"
            f"{example.to_string(index=False)}"
        )

    if (frame["season"] == EXCLUDED_SEASON).any():
        problems.append(f"season {EXCLUDED_SEASON} is present; the pack excludes it")

    if problems:
        raise ContractError("training data contract failed:\n  - " + "\n  - ".join(problems))
