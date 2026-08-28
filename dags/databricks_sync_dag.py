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
import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from src.alerting import failure_callback
from src.load_raw_to_databricks import all_endpoints, sync
from src.warehouse_usage import measured

DBT_PROJECT_DIR = "/opt/airflow/project/dbt"

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
    # A STALLED TASK MUST NOT OUTLIVE ITS OWN SCHEDULE. This DAG is daily, and nothing here
    # bounded a run: on 23 August one task blocked for over 17 minutes inside a single socket
    # read and was killed by the scheduler's heartbeat timeout rather than by any limit of
    # its own — which is a worse way to end, because it produces no summary and no traceback.
    # The whole of 28 August's work took 20 minutes across all three tasks, so 45 is generous
    # for the slowest of them while still guaranteeing the run cannot reach tomorrow's.
    "execution_timeout": timedelta(minutes=45),
    "on_failure_callback": failure_callback,
}


def sync_to_databricks(**context):
    """Load whatever Databricks is missing, and refuse to call a partial load a success."""
    with measured("raw_sync"):
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


def run_dbt(command: str, **context):
    """Run one dbt command against the analytics warehouse, metering the time it costs.

    `--target databricks` is explicit because the profile's default target is Postgres.
    That default is the safety property: this DAG is the only place in the stack that can
    spend warehouse time, and it has to ask for it by name.

    `measured` wraps the whole invocation rather than each model — the quota is consumed by
    warehouse *uptime*, and on a 160-node build the cold start dominates.

    `tag:postgres_only` is excluded because cfdb's own telemetry — dbt test outcomes and
    warehouse timings — is written straight to Postgres and has no Databricks source table.
    Operational history belongs where the operations are.
    """
    result = subprocess.run(
        ["dbt", command, "--project-dir", DBT_PROJECT_DIR, "--target", "databricks",
         "--exclude", "tag:postgres_only"],
        cwd="/opt/airflow/project", capture_output=True, text=True,
    )
    # dbt's own output is the diagnosis when this fails; printing it puts the failing model
    # in the task log instead of only a return code.
    print(result.stdout[-4000:])
    if result.returncode != 0:
        print(result.stderr[-2000:])
        raise RuntimeError(f"dbt {command} against Databricks failed "
                           f"(exit {result.returncode})")
    return {"command": command}


def metered_dbt(command: str, **context):
    with measured(f"dbt_{command}"):
        return run_dbt(command, **context)


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
    sync_raw = PythonOperator(
        task_id="sync_raw_to_databricks",
        python_callable=sync_to_databricks,
    )

    # dbt against the analytics warehouse, once the raw layer underneath it is level.
    # `--target databricks` is explicit: the profile's default target is Postgres, so this
    # is the only place in the stack that can spend warehouse time by accident.
    #
    # `measured` wraps the *whole* dbt invocation rather than each model, because the
    # quota is consumed by warehouse uptime and the cold start dominates a 160-node build.
    dbt_run = PythonOperator(
        task_id="dbt_run_databricks",
        python_callable=metered_dbt,
        op_kwargs={"command": "run"},
    )
    dbt_test = PythonOperator(
        task_id="dbt_test_databricks",
        python_callable=metered_dbt,
        op_kwargs={"command": "test"},
    )

    sync_raw >> dbt_run >> dbt_test
