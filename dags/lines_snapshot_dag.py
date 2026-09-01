"""Airflow DAG: periodic betting-line snapshots.

CFBD serves the *current* line plus an opening value. The path between them exists only if
we sample it, and once a game kicks off it can never be recovered — this is the one part of
the pipeline where a missed run is permanently lost data, not a delayed backfill. Closing
Line Value is built entirely from that history.

Cadence
-------
The schedule is permanently the finest cadence — `0 */4 * * *` UTC — and each run is gated
by `src.lines_cadence.should_snapshot`:

    inside the season window   -> every run proceeds       (4-hourly)
    outside it                 -> only the 00:00 UTC run   (daily)

Deliberately *not* implemented by changing the schedule seasonally. A seasonal schedule edit
is a runtime-path change twice a year, and one August it will be forgotten. Between seasons
the only maintenance is three dates in `config/lines_cadence.json`; this file never changes.

Tasks
-----
    cadence_gate -> snapshot_lines -> load_to_postgres

The snapshot and the load are separate on purpose. The fetch is the irreversible part: if
the load fails, history has still been captured to disk and the next run is unaffected — the
load simply catches up. Coupling them would let a database problem cost us line movement.

Boundaries
----------
This DAG schedules, gates and retries. It performs no transforms and computes no metrics:
tasks call `src.*` functions that land a raw response and load it verbatim. Meaning is
dbt's job downstream.
"""
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    ShortCircuitOperator,
)
from airflow.utils.trigger_rule import TriggerRule

from src.alerting import failure_callback
from src.lines_cadence import load_config, should_snapshot
from src.load_raw_to_postgres import load_endpoint
from src.snapshot import snapshot_lines

# Finest cadence, always. The gate below decides which runs actually do work.
SCHEDULE = "0 */4 * * *"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    "retries": 3,
    # Lines move continuously, so a failed run is worth retrying quickly — but there is no
    # point retrying for hours, since the next scheduled run supersedes it.
    "retry_delay": timedelta(minutes=5),
    # Data quality rule #5: failures are visible, never swallowed.
    "on_failure_callback": failure_callback,
}


def cadence_gate(**context) -> bool:
    """Decide whether this run should capture a snapshot.

    Logs the branch and the reason on *every* run, including skips. A short-circuit that
    skips silently is indistinguishable from a broken DAG when you look at it in March.
    """
    now = context.get("logical_date") or datetime.now(timezone.utc)
    config = load_config()
    decision = should_snapshot(now, config)

    print(
        f"cadence gate: {decision.branch.upper()} — proceed={decision.proceed} | "
        f"now={now.isoformat()} | {decision.reason}"
    )
    return decision.proceed


def take_snapshot(**context):
    """Land one snapshot of the week currently in play."""
    summary = snapshot_lines()
    print(f"lines snapshot: {summary}")
    return summary


def load_snapshots(**context):
    """Load every landed lines file into the warehouse.

    Loads the whole endpoint rather than only this run's file: the loader upserts on
    filename, so re-loading costs nothing, and any earlier snapshot that never reached the
    warehouse is swept up here instead of waiting for the weekly DAG.
    """
    load_endpoint("lines")
    return {"loaded": "lines"}


with DAG(
    dag_id="cfbd_lines_snapshot",
    description="Betting-line snapshots: 4-hourly in season, daily outside it",
    default_args=default_args,
    start_date=datetime(2026, 8, 15),
    schedule=SCHEDULE,
    # Never backfill: a snapshot is only meaningful at the moment it was taken, so a
    # catchup run would land today's lines stamped as though they were last week's.
    catchup=False,
    max_active_runs=1,
    tags=["cfdb", "lines", "snapshot"],
) as dag:
    gate = ShortCircuitOperator(
        task_id="cadence_gate",
        python_callable=cadence_gate,
        # `ignore_downstream_trigger_rules=False` SO THE HEARTBEAT CAN TELL THE
        # DIFFERENCE BETWEEN IDLE AND DEAD.
        #
        # With True, a closed gate skips every downstream task whatever trigger rule it
        # carries — including the heartbeat. The pipeline would then emit nothing all
        # off-season, and a dead-man's switch cannot distinguish "correctly idle" from
        # "the box is off". That is the exact confusion it exists to remove.
        #
        # With False, each downstream task applies its own rule: the work tasks default to
        # all_success and still skip behind a closed gate, unchanged, while the heartbeat
        # uses none_failed and so beats on a deliberate skip and stays silent on a failure.
        # A skipped gate is a normal outcome, not a failure.
        ignore_downstream_trigger_rules=False,
    )
    snapshot = PythonOperator(
        task_id="snapshot_lines",
        python_callable=take_snapshot,
    )
    load = PythonOperator(
        task_id="load_to_postgres",
        python_callable=load_snapshots,
        # One retry only: the next scheduled run loads this file anyway, so a stuck load
        # must not hold the slot against the next fetch.
        retries=1,
    )

    # The dead-man's switch. This DAG has no publish step — a lines snapshot is not
    # user-facing on its own — so `load` is the end of its success path.
    beat = PythonOperator(
        task_id="heartbeat",
        # NONE_FAILED, NOT the default all_success. This DAG is gated, so a run that
        # correctly decides to do nothing leaves every work task SKIPPED — and an
        # all_success heartbeat would stay silent through an entire off-season, which a
        # monitor cannot distinguish from a dead box. none_failed beats on success or
        # deliberate skip and stays silent the moment anything actually fails.
        trigger_rule=TriggerRule.NONE_FAILED,
        python_callable=lambda **c: __import__(
            "src.heartbeat", fromlist=["beat"]).beat(
                "lines_snapshot",
                dag_id=getattr(c.get("dag_run"), "dag_id", "") or "",
                run_id=getattr(c.get("dag_run"), "run_id", "") or ""),
    )

    gate >> snapshot >> load >> beat
