"""Airflow DAG: record what cfdb is spending against its metered dependencies.

Two quotas stand between this project and a silent stop, and neither announces itself:

  CFBD          75,000 calls/month on Tier 3, reported exactly by /info. Generous, but
                every cadence decision spends it, and the decisions accumulate.
  Databricks    Free Edition, no published threshold and no API to read consumption back.
                An overrun shuts compute down "for the rest of the day (and in extreme
                cases, the rest of the month)".

Neither is user-visible — the site reads serving Postgres, so exhausting either costs
freshness rather than availability. That is exactly why this is worth scheduling: a limit
you only notice when it bites is one you find out about from a stale dashboard days later.

Cost of running it: two API calls a day, roughly 60 a month against 75,000. The
measurement is 0.08% of the thing it measures.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from src.alerting import failure_callback
from src.ingest import fetch
from src.load_raw_to_postgres import load_endpoint
from src.warehouse_usage import load_to_postgres

# 13:00 UTC — an hour before the Databricks sync, so the day's warehouse measurements from
# the *previous* run are landed and the quota snapshot is not itself competing for the
# warehouse it is about to measure.
SCHEDULE = "0 13 * * *"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": failure_callback,
}


def snapshot_quota(**context):
    """Land /info and /info/usage as raw files.

    Both are registered in the endpoint registry with `include=False` — correctly, since
    they are metadata rather than data and have no business in a backfill. They are fetched
    explicitly here instead, which is the only place they belong.
    """
    fetch("info")
    # A 31-day window with a generous limit: the point of the per-endpoint breakdown is to
    # answer *which* cadence is expensive, and a short window hides the weekly DAGs.
    fetch("info/usage", {"days": 31, "limit": 50})
    return {"snapshotted": ["info", "info/usage"]}


def load_metrics(**context):
    """Load the quota snapshots and the warehouse meter into the warehouse."""
    load_endpoint("info")
    load_endpoint("info_usage")
    rows = load_to_postgres()
    return {"warehouse_usage_rows": rows}


with DAG(
    dag_id="cfbd_ops_metrics",
    description="Daily: snapshot CFBD quota and Databricks warehouse consumption",
    default_args=default_args,
    start_date=datetime(2026, 8, 18),
    schedule=SCHEDULE,
    # Each run records the position *now*; a backfill would land today's numbers stamped
    # as though they were last week's, which is precisely the error this DAG exists to
    # avoid making about quota.
    catchup=False,
    max_active_runs=1,
    tags=["cfdb", "ops", "quota"],
) as dag:
    snapshot = PythonOperator(task_id="snapshot_quota", python_callable=snapshot_quota)
    load = PythonOperator(task_id="load_metrics", python_callable=load_metrics)

    snapshot >> load
