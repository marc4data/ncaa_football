"""Measure how much Databricks warehouse time cfdb actually consumes.

Databricks Free Edition enforces an **undisclosed** usage quota. Databricks' own wording:
exceeding it means "your workspace's compute resources will be shut down and unavailable
for the rest of the day (and in extreme cases, the rest of the month)". Data survives;
compute does not.

That makes it an availability risk rather than a cost risk — the bill is always $0 — and
an unusual one, because the threshold is invisible until it is crossed. The only defence
is to know our own consumption before a shutdown teaches it to us.

**Why elapsed time, measured here, rather than actual DBUs.** Free Edition documents "no
access to the account console or account-level APIs", which is where billable usage would
normally be read from. Client-side elapsed seconds is therefore a proxy, not the real
figure — it counts wall-clock from connection to completion, including the cold start,
which is the dominant cost on a warehouse that auto-stops. It is an over-estimate of
compute time and an honest lower bound on *our* footprint. Treat the trend as the signal,
not the absolute number.

Append-only JSONL, matching `src/alerting.py`: no schema migration to start collecting, and
a dbt source can read it whenever `fct_api_usage` is built.
"""
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

USAGE_LOG = Path("data") / "metrics" / "warehouse_usage.jsonl"


def record(entry: Dict[str, Any], path: Optional[Path] = None) -> bool:
    """Append one measurement. Never raises — instrumentation must not break the pipeline."""
    path = path or USAGE_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception as exc:
        print(f"WAREHOUSE-USAGE: could not record ({exc})")
        return False


@contextmanager
def measured(operation: str, path: Optional[Path] = None, **context):
    """Time a block of warehouse work and record it, whether or not it succeeds.

    A failed run still consumed warehouse time — often *more*, because it paid the cold
    start and then died. Recording only successes would understate consumption in exactly
    the situation where consumption matters.
    """
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    outcome = "success"
    try:
        yield
    except BaseException:
        outcome = "failed"
        raise
    finally:
        elapsed = round(time.monotonic() - started, 1)
        record({
            "at": started_at,
            "operation": operation,
            "outcome": outcome,
            "elapsed_seconds": elapsed,
            "catalog": os.getenv("DATABRICKS_CATALOG", "workspace"),
            **context,
        }, path)
        print(f"WAREHOUSE-USAGE: {operation} {outcome} in {elapsed}s")


def summary(path: Optional[Path] = None) -> Dict[str, Any]:
    """Totals so far, for a freshness panel or a quick look before a heavy backfill."""
    path = path or USAGE_LOG
    if not path.exists():
        return {"runs": 0, "total_seconds": 0.0, "total_hours": 0.0}

    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            # One malformed line must not blind the whole meter.
            continue

    total = sum(float(e.get("elapsed_seconds") or 0) for e in entries)
    return {
        "runs": len(entries),
        "failed_runs": sum(1 for e in entries if e.get("outcome") == "failed"),
        "total_seconds": round(total, 1),
        "total_hours": round(total / 3600, 2),
        "first_at": entries[0].get("at") if entries else None,
        "last_at": entries[-1].get("at") if entries else None,
    }


def load_to_postgres(path: Optional[Path] = None) -> int:
    """Land the measurement log into `raw.raw_warehouse_usage` so dbt can read it.

    Idempotent on (at, operation): the log is append-only and this is re-run daily over the
    whole file, so re-loading must cost nothing rather than duplicating history. The pair
    is a safe key because a single operation cannot start twice at the same instant.

    Deliberately not a CFBD endpoint, but it lands in `raw` for the same reason those do:
    it is unmodelled source data, and dbt owns everything downstream of it.
    """
    from .load_raw_to_postgres import get_conn

    path = path or USAGE_LOG
    if not path.exists():
        return 0

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append((entry.get("at"), entry.get("operation"), entry.get("outcome"),
                     entry.get("elapsed_seconds"), entry.get("catalog")))
    if not rows:
        return 0

    connection = get_conn()
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw.raw_warehouse_usage (
                    observed_at timestamptz NOT NULL,
                    operation text NOT NULL,
                    outcome text,
                    elapsed_seconds numeric,
                    catalog text,
                    PRIMARY KEY (observed_at, operation)
                )
            """)
            cursor.executemany("""
                INSERT INTO raw.raw_warehouse_usage
                    (observed_at, operation, outcome, elapsed_seconds, catalog)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (observed_at, operation) DO UPDATE
                    SET outcome = EXCLUDED.outcome,
                        elapsed_seconds = EXCLUDED.elapsed_seconds
            """, rows)
        return len(rows)
    finally:
        connection.close()


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
