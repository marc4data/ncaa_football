"""Land model prediction exports into the raw layer.

The CFB Model Training Pack ships `Prediction_Export_Schema_2026.md`, a 42-column contract
that all seven modelling notebooks write to. This loads those CSVs verbatim — it is a load
job, not a design job, and the contract is adopted rather than reinterpreted.

**The sign convention is preserved exactly and is not flipped here or anywhere downstream.**
The pack uses, and this has been verified against all 5,133 training rows:

    actual_margin = away_points - home_points     <- AWAY MINUS HOME
    margin < 0 means the HOME team won
    spread  < 0 means the HOME team was favoured  (verified: home wins 74.4% of those
                                                   games, versus 31.4% when spread > 0)

That is inverted from the intuitive reading. A silent flip mid-pipeline would invert every
cover flag, every edge and every ATS figure while still looking entirely plausible, so the
convention travels untouched through raw and staging; a home-perspective margin is derived
in the serving layer as an explicitly named column.

**Licensing.** `cfdb_model_pack/` is personal, non-commercial, original-purchaser-only and
must never be committed. `model_outputs/` holds derived run artifacts and is gitignored with
it. This module reads them from disk and never writes them back.

Versioning. `model_version` is the first 12 hex characters of the file's SHA-256, and
`prediction_ts` is its modification time. That makes a reload of the same file idempotent
and a re-scored file a new version that APPENDS — so Model Performance can never be
silently rewritten by a retrain.

Usage:
  python -m src.load_predictions                 # every expected file in model_outputs/
  python -m src.load_predictions --dir some/dir
"""
import argparse
import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# The notebooks use a RELATIVE output path — Path("model_outputs") — and a notebook runs
# from its own directory, so exports land under cfdb_model_pack/ rather than the repo root.
# Both are searched, in order, because getting this wrong looks exactly like "the notebooks
# have not been run yet": a clean exit reporting zero files.
CANDIDATE_DIRS = (
    Path("model_outputs"),
    Path("cfdb_model_pack") / "model_outputs",
)
OUTPUT_DIR = CANDIDATE_DIRS[0]


# Named in the pack's schema doc under "Expected Local Files". Listed explicitly rather than
# globbed so a stray CSV in the directory is not silently ingested as predictions.
EXPECTED_FILES = (
    "linear_margin_predictions.csv",
    "random_forest_score_predictions.csv",
    "xgboost_wp_predictions.csv",
    "fastai_wp_predictions.csv",
    "logistic_wp_predictions.csv",
    "shap_xgboost_wp_predictions.csv",
    "ensemble_predictions.csv",
)

# The 42 columns, in the contract's order. Kept as a tuple so a schema drift is detected by
# comparing against it rather than by whatever the first file happened to contain.
CONTRACT_COLUMNS = (
    "game_id", "season", "season_type", "week", "start_date", "neutral_site",
    "home_team", "away_team", "home_conference", "away_conference",
    "split", "model_name", "model_family", "target",
    "home_points", "away_points", "actual_margin", "actual_total_points",
    "actual_home_win", "actual_winner", "spread", "actual_home_cover",
    "predicted_home_points", "predicted_away_points", "predicted_margin",
    "predicted_total_points", "predicted_home_win_probability",
    "raw_home_win_probability", "calibrated_home_win_probability",
    "predicted_home_win", "predicted_winner", "predicted_home_cover",
    "market_implied_home_win_probability", "home_win_probability_edge",
    "home_cover_edge", "confidence_bucket", "margin_error", "absolute_margin_error",
    "home_win_correct", "cover_correct", "brier_score_component", "log_loss_component",
)


def resolve_directory(explicit: Optional[Path] = None) -> Optional[Path]:
    """First candidate directory that actually holds an expected export."""
    if explicit is not None:
        return explicit if explicit.exists() else None
    for candidate in CANDIDATE_DIRS:
        if candidate.exists() and any((candidate / n).exists() for n in EXPECTED_FILES):
            return candidate
    # Nothing populated: report against the first that exists, so the message names a real path.
    for candidate in CANDIDATE_DIRS:
        if candidate.exists():
            return candidate
    return None


DDL = """
CREATE TABLE IF NOT EXISTS raw.raw_model_prediction (
    source_file text NOT NULL,
    model_version text NOT NULL,
    prediction_ts timestamptz NOT NULL,
    row_number int NOT NULL,
    payload jsonb NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_file, model_version, row_number)
)
"""


def file_version(path: Path) -> str:
    """First 12 hex chars of the file's SHA-256.

    Content-addressed on purpose: the same export reloaded is the same version and costs
    nothing, while a re-scored export is a different version and lands alongside the old one
    instead of overwriting it.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def read_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def check_contract(path: Path, rows: List[Dict[str, str]]) -> List[str]:
    """Report columns the contract expects and the file does not have.

    A warning rather than a refusal: the schema says to leave unsupported fields blank, and
    a margin model legitimately has nothing to put in the probability columns. A *missing
    column* is still worth saying out loud, because it is how a renamed field would show up.
    """
    if not rows:
        return []
    present = set(rows[0].keys())
    return [c for c in CONTRACT_COLUMNS if c not in present]


def load_file(cursor, path: Path) -> int:
    """Land one prediction export. Returns rows written."""
    import json

    rows = read_rows(path)
    if not rows:
        print(f"  {path.name}: empty, skipped")
        return 0

    missing = check_contract(path, rows)
    if missing:
        print(f"  {path.name}: WARNING — {len(missing)} contract column(s) absent: "
              f"{', '.join(missing[:6])}{'...' if len(missing) > 6 else ''}")

    version = file_version(path)
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    payloads = [
        (path.name, version, ts, i, json.dumps(row))
        for i, row in enumerate(rows)
    ]
    cursor.executemany("""
        INSERT INTO raw.raw_model_prediction
            (source_file, model_version, prediction_ts, row_number, payload)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_file, model_version, row_number) DO NOTHING
    """, payloads)
    print(f"  {path.name}: {len(rows)} row(s), version {version}")
    return len(rows)


def load_directory(directory: Optional[Path] = None) -> Dict[str, int]:
    from .load_raw_to_postgres import get_conn

    directory = resolve_directory(directory)
    if directory is None:
        searched = " or ".join(str(c) for c in CANDIDATE_DIRS)
        print(f"No prediction directory found ({searched}) — run the pack's notebooks first.")
        return {"files": 0, "rows": 0}
    print(f"Reading from {directory}")

    present = [directory / name for name in EXPECTED_FILES if (directory / name).exists()]
    if not present:
        print(f"No expected prediction files in {directory}. Expected any of: "
              f"{', '.join(EXPECTED_FILES)}")
        return {"files": 0, "rows": 0}

    connection = get_conn()
    total = 0
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cursor.execute(DDL)
            for path in present:
                total += load_file(cursor, path)
    finally:
        connection.close()
    return {"files": len(present), "rows": total}


def load_directory_to_databricks(directory: Optional[Path] = None) -> Dict[str, int]:
    """Mirror the prediction exports into Databricks.

    Predictions build on BOTH engines (decision log 2026-08-19): the licensed dataset is
    never uploaded anywhere — only derived output, which the licence explicitly permits for
    private projects, and which carries none of the pack's 86 training features.

    Same content-addressed idempotency as the Postgres path: MERGE on
    (source_file, model_version, row_number), so re-running costs a query and changes
    nothing, and a re-scored export lands alongside its predecessor.
    """
    import json
    from .load_raw_to_databricks import connect, CATALOG, SCHEMA, _sql_string

    directory = resolve_directory(directory)
    if directory is None:
        return {"files": 0, "rows": 0}
    present = [directory / name for name in EXPECTED_FILES if (directory / name).exists()]
    if not present:
        return {"files": 0, "rows": 0}

    total = 0
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_model_prediction (
                    source_file STRING, model_version STRING, prediction_ts TIMESTAMP,
                    row_number INT, payload STRING, loaded_at TIMESTAMP
                ) USING DELTA
            """)
            for path in present:
                rows = read_rows(path)
                if not rows:
                    continue
                version = file_version(path)
                ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
                # Delete-then-insert for this (file, version): simpler than a row-wise MERGE
                # and identical in effect, because the pair is content-addressed — the same
                # version always carries the same rows.
                cursor.execute(
                    f"DELETE FROM {CATALOG}.{SCHEMA}.raw_model_prediction "
                    f"WHERE source_file = {_sql_string(path.name)} "
                    f"AND model_version = {_sql_string(version)}")
                values = ", ".join(
                    f"({_sql_string(path.name)}, {_sql_string(version)}, "
                    f"cast({_sql_string(ts)} as timestamp), {i}, "
                    f"{_sql_string(json.dumps(row))}, current_timestamp())"
                    for i, row in enumerate(rows))
                cursor.execute(
                    f"INSERT INTO {CATALOG}.{SCHEMA}.raw_model_prediction VALUES {values}")
                print(f"  {path.name}: {len(rows)} row(s) -> Databricks")
                total += len(rows)
    return {"files": len(present), "rows": total}


def main() -> int:
    parser = argparse.ArgumentParser(description="Load model prediction exports.")
    # Default None, not OUTPUT_DIR: a default here would look like an explicitly requested
    # path and skip the candidate search entirely — which is exactly the bug that made this
    # report "0 files" while six exports sat in cfdb_model_pack/model_outputs.
    parser.add_argument("--dir", type=Path, default=None)
    parser.add_argument("--databricks", action="store_true",
                        help="also mirror into Databricks")
    args = parser.parse_args()
    summary = load_directory(args.dir)
    print(f"Loaded {summary['rows']} row(s) from {summary['files']} file(s) into Postgres")
    if args.databricks:
        db = load_directory_to_databricks(args.dir)
        print(f"Loaded {db['rows']} row(s) from {db['files']} file(s) into Databricks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
