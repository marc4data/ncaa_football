"""Land dbt's own run artifacts so test outcomes become queryable history.

dbt writes `target/run_results.json` on every invocation and then overwrites it on the next
one. That makes the current state visible and the *trend* invisible — which is backwards for
data quality, where the useful questions are all historical: is this test newly failing, how
long has it been failing, which model fails most often, did the failure start when the
source changed.

Landing each invocation keeps that history. One row per test per invocation, keyed on
(invocation_id, unique_id): dbt generates a fresh invocation_id per run, so re-loading the
same artifact is idempotent and loading a rerun appends rather than overwrites.

Deliberately not a CFBD endpoint, but it lands in `raw` for the same reason those do: it is
unmodelled source data, and dbt owns everything downstream of it.

Usage:
  python -m src.dbt_artifacts                    # load dbt/target/run_results.json
  python -m src.dbt_artifacts --path other.json
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

DEFAULT_ARTIFACT = Path("dbt") / "target" / "run_results.json"

DDL = """
CREATE TABLE IF NOT EXISTS raw.raw_dbt_test_result (
    invocation_id text NOT NULL,
    unique_id text NOT NULL,
    generated_at timestamptz,
    dbt_version text,
    status text,
    failures bigint,
    execution_time numeric,
    message text,
    relation_name text,
    PRIMARY KEY (invocation_id, unique_id)
)
"""


def load_run_results(path: Optional[Path] = None) -> int:
    """Load one run_results.json into raw.raw_dbt_test_result. Returns rows written."""
    from .load_raw_to_postgres import get_conn

    path = path or DEFAULT_ARTIFACT
    if not path.exists():
        print(f"No dbt artifact at {path}")
        return 0

    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A truncated artifact means the run died mid-write. Say so rather than loading a
        # partial picture of which tests passed.
        print(f"Artifact at {path} is not valid JSON ({exc}); refusing to load it")
        return 0

    metadata = artifact.get("metadata") or {}
    invocation_id = metadata.get("invocation_id")
    if not invocation_id:
        print("Artifact carries no invocation_id; refusing to load it")
        return 0

    rows = []
    for result in artifact.get("results") or []:
        unique_id = result.get("unique_id") or ""
        # Tests only. Model build results are already visible as Airflow task outcomes, and
        # mixing them in would make a "failure rate" mean two different things at once.
        if not unique_id.startswith("test."):
            continue
        rows.append((
            invocation_id,
            unique_id,
            metadata.get("generated_at"),
            metadata.get("dbt_version"),
            result.get("status"),
            result.get("failures"),
            result.get("execution_time"),
            (result.get("message") or None),
            result.get("relation_name"),
        ))

    if not rows:
        print("Artifact contained no test results")
        return 0

    connection = get_conn()
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cursor.execute(DDL)
            cursor.executemany("""
                INSERT INTO raw.raw_dbt_test_result
                    (invocation_id, unique_id, generated_at, dbt_version, status,
                     failures, execution_time, message, relation_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (invocation_id, unique_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        failures = EXCLUDED.failures,
                        execution_time = EXCLUDED.execution_time,
                        message = EXCLUDED.message
            """, rows)
        return len(rows)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load dbt run artifacts into the warehouse.")
    parser.add_argument("--path", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    written = load_run_results(args.path)
    print(f"Loaded {written} test result(s) from {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
