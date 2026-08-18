"""Airflow DAG: bring Databricks level with the local raw layer, once a day.

Every other load path writes to Postgres. Databricks — the analytics warehouse — was
caught up by hand, which is the kind of chore that is remembered in August and forgotten in
November. This closes that gap on a schedule.

Why daily, and not on every lines snapshot
------------------------------------------
Games are overwhelmingly Saturday (84.6% of FBS regular-season games in 2024-25), with
Thursday and Friday tails and a November MAC weeknight package. Lines are the only thing
that moves continuously, and they move for the *site*, which reads serving Postgres and
never reads Databricks. So Databricks needs completeness, not latency, and a daily sweep
delivers it at a sixth of the warehouse startups a per-snapshot load would cost.

Why every endpoint, not just the ones that change
-------------------------------------------------
`sync` establishes what is outstanding with a single query over the whole manifest, then
opens a connection only for endpoints that actually owe files. An idle endpoint therefore
costs one row in one query — so restricting the list would buy nothing and would quietly
strand any endpoint left off it.

Boundaries
----------
This DAG schedules and reports. The loading, the batching, the retry-per-endpoint and the
decision about what is outstanding all live in `src/load_raw_to_databricks.py`, where they
are testable without an Airflow instance.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from src.alerting import failure_callback
from src.load_raw_to_databricks import all_endpoints, sync

# 14:00 UTC: two hours after the Sunday results refresh and the Tuesday pre-game refresh,
# so the day's new files are already on disk when this runs rather than being picked up a
# day late.
SCHEDULE = "0 14 * * *"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    # `sync` already retries each endpoint three times against a warehouse that is expected
    # to be flaky. A second DAG-level attempt covers the run failing outright; more would
    # just be the same warehouse, still cold.
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
    "on_failure_callback": failure_callback,
}


def sync_to_databricks(**context):
    """Load whatever Databricks is missing, and refuse to call a partial load a success."""
    summary = sync(all_endpoints())
    print(f"databricks sync: {summary}")

    if summary["failed"]:
        # Data quality rule #5: failures are visible, never swallowed. A sync that loaded
        # nine endpoints and lost one is not a success, and the next run must not treat
        # the missing files as though they had landed.
        raise RuntimeError(
            f"{len(summary['failed'])} endpoint(s) failed to load: "
            f"{', '.join(summary['failed'])}"
        )
    return summary


with DAG(
    dag_id="cfbd_databricks_sync",
    description="Daily: load raw files Databricks is missing",
    default_args=default_args,
    start_date=datetime(2026, 8, 18),
    schedule=SCHEDULE,
    # Nothing here is time-addressed — the run loads whatever is outstanding at the moment
    # it runs — so a backfill would repeat identical no-op work.
    catchup=False,
    max_active_runs=1,
    tags=["cfdb", "databricks", "raw"],
) as dag:
    PythonOperator(
        task_id="sync_raw_to_databricks",
        python_callable=sync_to_databricks,
    )
