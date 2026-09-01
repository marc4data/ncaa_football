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
from src.dbt_artifacts import load_run_results
from src.load_raw_to_postgres import load_endpoint
from src.publish_marts import publish_all
from src.weekly import pregame_refresh, results_refresh

DBT_PROJECT_DIR = "/opt/airflow/project/dbt"

# The production refresh builds an EXPLICIT selection, never the whole project.
#
# `+tag:production` now resolves to 53 of the project's 58 models: every serving view, plus
# every mart and staging model that feeds one. The serving layer carries the tag from
# dbt_project.yml, so it applies by construction rather than one model at a time, and `+`
# pulls the ancestors.
#
# It used to resolve to SIX — three legacy marts and three staging models, not one srv_
# view. The refresh fetched results every Sunday, landed them in raw, rebuilt three marts
# that nothing on the site reads, and stopped. Every view the site actually serves was
# rebuilt only when somebody ran dbt by hand, which meant the pipeline was scheduled up to
# the point where it stopped mattering.
#
# The narrow selector existed to keep half-finished work out of the runtime path. That
# concern is real and is already answered twice over: Airflow reads a worktree PINNED TO
# MAIN, and CI builds the entire project on every pull request, so unfinished work cannot
# reach the tree this runs against. Five models remain excluded — dim_season, dim_venue,
# dim_week, stg_calendar, stg_venues — because no serving view reads them, which is exactly
# the property the selector is supposed to have.
# Two tags, two meanings. `+tag:production` is the site's surface and everything it
# depends on. `tag:warehouse` is every staging model, whether or not a page reads it —
# without it, a staging model for an endpoint no page consumes is never built, which is
# most of prompt 029's Priority 3. Space-separated selectors union in dbt.
PRODUCTION_SELECTOR = "--select +tag:production tag:warehouse"

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


def _heartbeat(name):
    """A final task that beats ONLY when everything upstream succeeded.

    `trigger_rule` is left at its default `all_success` on purpose, and that default is the
    entire safety property: a heartbeat from a failed run is a lie, and the one existing
    task in this project that uses `all_done` — capture_dq — is the counter-example that
    made the distinction concrete. If this task ever needs to run on failure, the heartbeat
    is the wrong thing to attach to it.
    """
    def _beat(**context):
        from src import heartbeat
        run = context.get("dag_run")
        heartbeat.beat(name,
                       dag_id=getattr(run, "dag_id", "") or "",
                       run_id=getattr(run, "run_id", "") or "")

    return PythonOperator(task_id="heartbeat", python_callable=_beat)


# One cadence name per DAG. These are the strings the external monitor knows: each maps to a
# CFDB_HEARTBEAT_URL_<NAME> env var, so silencing one for the required absence test is a
# config change rather than a code change.
HEARTBEAT_NAME = {
    "cfbd_results_refresh": "weekly_results",
    "cfbd_pregame_refresh": "weekly_pregame",
    "cfbd_midweek_results": "weekly_midweek",
}


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
            bash_command=f"dbt run --project-dir {DBT_PROJECT_DIR} {PRODUCTION_SELECTOR}",
        )
        dbt_test = BashOperator(
            task_id="dbt_test",
            bash_command=f"dbt test --project-dir {DBT_PROJECT_DIR} {PRODUCTION_SELECTOR}",
        )

        # PUBLISH IS A DOWNSTREAM TASK, NOT A SCHEDULE.
        #
        # This is the last hop before a user sees anything, and until now it had no
        # scheduled trigger at all: the serving database changed only when someone ran
        # publish_marts by hand. Every model could be current and the site still weeks old.
        #
        # It runs after dbt_test rather than on its own clock, and the difference is not
        # cosmetic. A clock-triggered publish can fire mid-build and ship a half-rebuilt
        # serving layer — succeeding while doing it, which is the same green-and-wrong
        # signature as the three defects found this week. Being downstream makes
        # "the build finished" a precondition rather than a hope.
        #
        # all_success is the right trigger here, unlike capture_test_results below: a
        # failing dbt test means the serving layer is not fit to publish, and shipping it
        # anyway would put data on the site that dbt has just said is wrong.
        publish = PythonOperator(
            task_id="publish_to_serving",
            python_callable=lambda **_: publish_all(),
        )

        capture_dq = PythonOperator(
            task_id="capture_test_results",
            python_callable=lambda **_: load_run_results(),
            # all_done, not all_success. A failing dbt test is exactly when this history is
            # worth having, and the default rule would skip the capture in precisely that
            # case — recording only the runs where nothing went wrong.
            trigger_rule="all_done",
        )

        # CAPTURE HANGS OFF dbt_test, NOT OFF publish, AND THAT IS WHAT MAKES THE RUN HONEST.
        #
        # A DagRun takes its state from its LEAF tasks. While this was a single chain ending
        # `publish >> capture_dq`, capture_dq — correctly `all_done` — succeeded whether or
        # not publish had run, and being the only leaf it reported the whole run as SUCCESS.
        #
        # That is exactly the green-and-wrong signature this project keeps finding. Between
        # 23 and 28 August every weekly refresh reported success while publish was
        # `upstream_failed` behind a red dbt test, and the site sat five days stale with
        # nothing on the DAG list saying so. The publish is the point of the pipeline; a run
        # that skips it has not succeeded, whatever the last task did.
        #
        # Fanning the two out makes publish a leaf in its own right, so its failure reaches
        # the run state — while capture_dq still records test history on every outcome,
        # which is the property its trigger rule exists to guarantee. capture_dq does not
        # read anything publish writes, so the ordering was incidental to begin with.
        # THE DEAD-MAN'S SWITCH, ON THE SUCCESS PATH ONLY.
        #
        # Downstream of publish, so it beats only when the whole chain worked — fetch, load,
        # transform, test AND the hop that puts data in front of a reader. A heartbeat any
        # earlier would report health for a run that never reached the site.
        #
        # Deliberately NOT downstream of capture_dq, which is `all_done` and therefore
        # succeeds after a failure. Attaching the beat there would make it say "alive" on
        # exactly the runs it exists to catch.
        beat = _heartbeat(HEARTBEAT_NAME[dag_id])

        dbt_test >> capture_dq
        fetch >> load >> dbt_run >> dbt_test >> publish >> beat
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
