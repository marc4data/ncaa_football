"""Airflow DAGs: the in-season weekly cadence.

Three schedules, on calendar days rather than CFBD week boundaries. That distinction is
load-bearing: CFBD's week 1 spans twelve days and two Saturdays, so a per-CFBD-week
trigger would sit idle through the opening slate.

  Sunday   — results refresh: the week just played (and the one before it, for late stat
             corrections), plus the ratings and cumulative stats that revise because of it.
  Tuesday  — pre-game refresh: lines and pre-game win probability for the upcoming week,
             plus ratings again, since polls publish early in the week.
  Thursday — mid-week results: the weeknight games Sunday is too late for.

Why a third run exists
----------------------
College football is overwhelmingly a Saturday sport — 84.6% of FBS regular-season kickoffs
in 2024-25 — which makes it easy to assume Sunday catches everything. It does not. The MAC
plays a November weeknight package, and across those two seasons 64 games kicked on a
Tuesday or Wednesday: more than Thursday and Sunday combined. With only a Sunday run, a
Tuesday-night result sat unrecorded for five days while the site showed the game as not
yet played.

Thursday 12:00 UTC is the slot that works, and the margins are the reason. Tuesday and
Wednesday games kick between 23:00 and 00:30 UTC and are finished by roughly 03:00 UTC the
following day, so a 12:00 UTC Thursday run is comfortably after them. It is also
comfortably *before* Thursday's own kickoffs at 22:00 UTC — which matters more than it
looks, because a refresh landing mid-slate would record live games as final.

Each DAG runs fetch -> load -> dbt run -> dbt test. Airflow schedules the transform; it
does not perform it. A failing dbt test fails the run, which is the intended split: data
correctness is dbt's, process reliability is Airflow's.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

from src.alerting import failure_callback
from src.load_raw_to_postgres import load_endpoint
from src.weekly import pregame_refresh, results_refresh

DBT_PROJECT_DIR = "/opt/airflow/project/dbt"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
    # Data quality rule #5: failures are visible, never swallowed.
    "on_failure_callback": failure_callback,
}


def _fetch(refresh_callable, **context):
    summary = refresh_callable()
    print(f"refresh summary: {summary}")
    # Endpoints touched are handed to the load task so it reloads only what changed
    # rather than re-reading every raw file on disk.
    context["task_instance"].xcom_push(key="endpoints", value=summary.get("endpoints", []))
    return summary


def _load(**context):
    endpoints = context["task_instance"].xcom_pull(task_ids="fetch", key="endpoints") or []
    for endpoint in endpoints:
        load_endpoint(endpoint)
    return {"loaded": endpoints}


def build_dag(dag_id: str, schedule: str, description: str, refresh_callable) -> DAG:
    with DAG(
        dag_id=dag_id,
        description=description,
        default_args=default_args,
        start_date=datetime(2026, 8, 15),
        schedule=schedule,
        # No catchup: a refresh pulls current state, so a backdated run would land today's
        # data stamped as last week's.
        catchup=False,
        max_active_runs=1,
        tags=["cfdb", "weekly"],
    ) as dag:
        fetch = PythonOperator(
            task_id="fetch",
            python_callable=_fetch,
            op_kwargs={"refresh_callable": refresh_callable},
        )
        load = PythonOperator(task_id="load_to_postgres", python_callable=_load)

        # Airflow schedules dbt; it does not do the transforming. The models and their
        # tests are dbt's, and a failing test fails the run — data correctness belongs to
        # dbt, process reliability to Airflow.
        dbt_run = BashOperator(
            task_id="dbt_run",
            bash_command=f"dbt run --project-dir {DBT_PROJECT_DIR}",
        )
        dbt_test = BashOperator(
            task_id="dbt_test",
            bash_command=f"dbt test --project-dir {DBT_PROJECT_DIR}",
        )

        fetch >> load >> dbt_run >> dbt_test
    return dag


results_dag = build_dag(
    "cfbd_results_refresh",
    "0 12 * * 0",  # Sunday 12:00 UTC — after Saturday's late kickoffs have finished
    "Results refresh: the week just played plus what revises because of it",
    results_refresh,
)

pregame_dag = build_dag(
    "cfbd_pregame_refresh",
    "0 12 * * 2",  # Tuesday 12:00 UTC — after polls publish, before the next slate
    "Pre-game refresh: lines and ratings for the upcoming week",
    pregame_refresh,
)
# Same callable as Sunday, deliberately. The work is identical — refresh the weeks whose
# data can still change — and only the day differs. A separate "mid-week" fetch path would
# be a second definition of the same thing, free to drift from the first.
midweek_dag = build_dag(
    "cfbd_midweek_results",
    "0 12 * * 4",  # Thursday 12:00 UTC — after Tue/Wed games end, before Thursday's kick
    "Mid-week results: the Tuesday and Wednesday games Sunday is too late for",
    results_refresh,
)
