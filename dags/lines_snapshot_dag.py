"""Airflow DAG: periodic betting-line snapshots.

CFBD serves the *current* line plus an opening value. The path between them exists only if
we sample it, and once a game kicks off that path can never be recovered — this is the one
part of the pipeline where a missed run is permanently lost data, not a delayed backfill.

Cadence
-------
Daily to start. Raising it to hourly is a one-line change to SCHEDULE below: the snapshot
targets the week currently in play (~0.11 MB per call), so hourly costs ~2.6 MB and 24 API
calls a day — about 320 MB across a season against a 75,000-call monthly quota.

Boundaries
----------
This DAG schedules and retries. It performs no transforms and computes no metrics: the
task calls `src.snapshot.snapshot_lines`, which lands a raw response and nothing more.
Meaning is dbt's job downstream.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.snapshot import snapshot_lines

# Change to "@hourly" if line movement proves interesting enough to sample more finely.
SCHEDULE = "@daily"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    "retries": 3,
    # Lines move continuously, so a failed run is worth retrying quickly — but there is no
    # point retrying for hours, since the next scheduled run supersedes it.
    "retry_delay": timedelta(minutes=5),
}


def take_snapshot(**context):
    """Land one snapshot of the week currently in play.

    Returns the summary so it lands in XCom and the task log — enough to see whether a run
    captured anything without opening the raw files.
    """
    summary = snapshot_lines()
    print(f"lines snapshot: {summary}")
    return summary


with DAG(
    dag_id="cfbd_lines_snapshot",
    description="Periodic betting-line snapshots for the week in play",
    default_args=default_args,
    start_date=datetime(2026, 8, 15),
    schedule=SCHEDULE,
    # Never backfill: a snapshot is only meaningful at the moment it was taken, so a
    # catchup run would land today's lines stamped as though they were last week's.
    catchup=False,
    max_active_runs=1,
    tags=["cfdb", "lines", "snapshot"],
) as dag:
    PythonOperator(
        task_id="snapshot_lines",
        python_callable=take_snapshot,
    )
