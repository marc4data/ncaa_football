"""Airflow DAG: the game spine, refreshed while games are finishing.

THE GAP THIS CLOSES. The three weekly DAGs are Sunday, Tuesday and Thursday, and the
Thursday one fires at 12:00 UTC — ten hours BEFORE Thursday's 22:00 kickoffs. So the twenty
games of Thursday 27 August would be marked "scheduled" on the site until Sunday 30 August,
and Saturday's fifty-one would sit unresolved from the final whistle until Sunday lunchtime.
Scores is the most-visited surface on any sports site during a game week, and a Scores page
showing yesterday's games as upcoming is worse than not having the page.

The answer is not a fourth fixed day. This is scheduled every two hours and gated at
runtime on whether a game has actually kicked off recently, so it collects continuously
through a game weekend and stays quiet on a Tuesday in October.

WHAT IT DELIBERATELY DOES NOT DO. It fetches /games and nothing else — two requests, for the
week in play and the one before it. A full results_refresh is 31 requests covering plays,
drives, box scores, PPA and ratings, and running that on this cadence would spend roughly
half the monthly quota re-fetching data that does not change between Saturday night and
Sunday morning. Cheap is what makes it frequent. The heavy refresh stays weekly and this
one keeps the scoreboard honest in between.

It runs the same publish chain as the weekly DAGs, because a fresh fct_game that never
reaches the droplet has not helped anybody:

    cadence_gate -> fetch_scores -> load -> dbt_run -> dbt_test -> publish

dbt runs a NARROW selection here, not the full production set: this DAG only ever changes
the game spine, and rebuilding every rating and season stat would make a two-request fetch
cost a full transform.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import (
    PythonOperator, ShortCircuitOperator,
)

from src.alerting import failure_callback
from src.lines_cadence import load_config
from src.load_raw_to_postgres import load_endpoint
from src.publish_marts import publish_all
from src.scores_cadence import hours_since_last_kickoff, should_refresh_scores
from src.weekly import scores_refresh

DBT_PROJECT_DIR = "/opt/airflow/project/dbt"

# Finest cadence, always. The gate below decides which runs do work, so the season is a
# config file rather than a schedule edit — the same pattern as cfbd_lines_snapshot, and for
# the same reason: a seasonal schedule change is a runtime-path change twice a year, and one
# August it gets forgotten.
SCHEDULE = "0 */2 * * *"

# What this DAG can change, and nothing else. `+` pulls ancestors, so this is the game spine
# and the views built on it. Deliberately NOT +tag:production — that is 53 models, and a
# two-request fetch has no business triggering a full transform every two hours.
SCORES_SELECTOR = (
    "--select +srv_scoreboard +srv_schedule +srv_matchup +srv_team_game_log +srv_today_edges"
)

# THE PARITY GATES CANNOT BE SATISFIED BY THIS DAG, SO THIS DAG MUST NOT RUN THEM.
#
# They compare a serving view against the LEGACY MART IT REPLACES — srv_team_game_log against
# mart_team_schedule, srv_standings against mart_team_season_record. The legacy mart is not an
# ancestor of the view that replaces it, so the selector above rebuilds one side and never the
# other, and the two drift a little further with every run. On 28 August that drift reached
# four team-rows and blocked the publish of an entire game day.
#
# This is not a tolerance for parity failing. The gates keep their full authority on the
# weekly refresh, which rebuilds +tag:production — both sides — and is the only place a parity
# comparison is meaningful. Running them here measured nothing except how long it had been
# since the last full build. Per the tests' own rule, the question when parity fails is which
# side is right, and a comparison between a fresh side and a stale one cannot answer it.
#
# They are scaffolding: both files are deleted when the marts they protect are dropped, and
# this exclusion goes with them.
TEST_EXCLUDE = "--exclude tag:parity"

default_args = {
    "owner": "cfdb",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": failure_callback,
}


def cadence_gate(**context) -> bool:
    """Ask whether there is anything to collect, and say why either way.

    A skip that explains itself is the difference between "quiet Tuesday" and "broken DAG"
    when you look at this in March.
    """
    now = datetime.now(tz=None).astimezone()
    decision = should_refresh_scores(
        now_utc=now,
        config=load_config(),
        hours_since_last_kickoff=hours_since_last_kickoff(),
    )
    print(f"scores cadence gate: {decision.branch.upper()} — "
          f"proceed={decision.proceed} | {decision.reason}")
    return decision.proceed


def _fetch(**context):
    summary = scores_refresh()
    print(f"scores refresh: {summary}")
    context["task_instance"].xcom_push(key="endpoints", value=summary.get("endpoints", []))
    return summary


def _load(**context):
    endpoints = context["task_instance"].xcom_pull(task_ids="fetch_scores",
                                                   key="endpoints") or []
    for endpoint in endpoints:
        load_endpoint(endpoint)
    return {"loaded": endpoints}


with DAG(
    dag_id="cfbd_scores_refresh",
    description="Game spine every 2h while games are settling; quiet otherwise",
    default_args=default_args,
    start_date=datetime(2026, 8, 15),
    schedule=SCHEDULE,
    # Never backfill: this fetches current state, so a catchup run would land today's
    # scores stamped as last week's.
    catchup=False,
    max_active_runs=1,
    tags=["cfdb", "scores"],
) as dag:
    gate = ShortCircuitOperator(
        task_id="cadence_gate",
        python_callable=cadence_gate,
        # A skipped gate is a normal outcome, not a failure.
        ignore_downstream_trigger_rules=True,
    )
    fetch = PythonOperator(task_id="fetch_scores", python_callable=_fetch)
    load = PythonOperator(task_id="load_to_postgres", python_callable=_load)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"dbt run --project-dir {DBT_PROJECT_DIR} {SCORES_SELECTOR}",
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(f"dbt test --project-dir {DBT_PROJECT_DIR} "
                      f"{SCORES_SELECTOR} {TEST_EXCLUDE}"),
    )
    # Serving only. The legacy marts are on the weekly cadence and this DAG does not touch
    # what they are built from.
    publish = PythonOperator(
        task_id="publish_to_serving",
        python_callable=lambda **_: publish_all(schemas=["serving"]),
    )

    gate >> fetch >> load >> dbt_run >> dbt_test >> publish
