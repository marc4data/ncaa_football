"""Airflow DAG: the game spine, refreshed while games are finishing.

THE GAP THIS CLOSES. The three weekly DAGs are Sunday, Tuesday and Thursday, and the
Thursday one fires at 12:00 UTC — ten hours BEFORE Thursday's 22:00 kickoffs. So the twenty
games of Thursday 27 August would be marked "scheduled" on the site until Sunday 30 August,
and Saturday's fifty-one would sit unresolved from the final whistle until Sunday lunchtime.
Scores is the most-visited surface on any sports site during a game week, and a Scores page
showing yesterday's games as upcoming is worse than not having the page.

The answer is not a fourth fixed day. This is scheduled every two hours and gated at
runtime on the schedule itself, so it collects continuously through a game weekend and
stays quiet on a Tuesday in October. The gate asks two questions, not one:

    did a game kick off recently          -> results are landing, collect
    is a known game STILL not final       -> it is delayed or suspended, collect

The second is not a refinement of the first. A Thursday game halted for lightning and
resumed Friday afternoon keeps its Thursday kickoff timestamp, so the kickoff clock says
eighteen hours and the settle window shut overnight — and the finished game would sit
unpublished until Sunday, which is the failure this DAG exists to prevent arriving through
the one door the kickoff clock does not watch. Bounded at 36 hours so a postponed game,
which is `completed = false` with a past kickoff forever, cannot hold the gate open.

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
from airflow.utils.trigger_rule import TriggerRule

from src.alerting import failure_callback
from src.lines_cadence import load_config
from src.load_raw_to_postgres import load_endpoint
from src.publish_marts import publish_all
from src.scores_cadence import schedule_state, should_refresh_scores
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

# A TEST THIS DAG CANNOT SATISFY IS A TEST THIS DAG MUST NOT RUN.
#
# THE RULE, stated once instead of discovered six times: this DAG fetches /games and rebuilds
# the five views above plus their ancestors. Nothing else. So any test comparing something it
# DOES refresh against something it does NOT is measuring the gap between two fetch times, not
# correctness — and it reports that gap as a failure on essentially every run.
#
# Two shapes qualify, and both were found the hard way:
#
#   a legacy mart      mart_team_schedule, mart_team_season_record are not ancestors of any
#                      of the five views, so this DAG refreshes one side of the comparison
#   another endpoint   /records is never refetched here, while fct_team_record advances with
#                      every game that finals — the asymmetry is permanent, not transient
#
# Six tests carry `full_refresh_only`. Five surfaced one at a time across the week of
# 24 August, each looking like a separate bug and each patched separately:
#
#   assert_schedule_matches_games                 blocked the first run after the dedup fix
#   assert_parity_srv_team_game_log               blocked a game day at four team-rows
#   assert_games_played_reconciles_to_schedule    blocked the 02:00 run on 29 August
#   assert_derived_record_matches_cfbd_records    blocked 28 August; would have blocked
#                                                 Saturday's slate too, for a different reason
#
# The sixth, assert_date_only_seasons_are_not_timezone_shifted, has never fired. It is tagged
# because it has the same shape, which is the point of fixing a class rather than an instance.
#
# NOT a tolerance for any of these failing. All six keep full authority on the weekly refresh,
# which rebuilds +tag:production and refetches every endpoint — the only place these
# comparisons mean anything. Per the parity gates' own rule, "which side is right" cannot be
# answered by comparing a fresh side to a stale one.
#
# Deliberately NOT tagged: tests that read only one side. Mart-only invariants
# (assert_wins_equal_losses_per_season, assert_record_totals_reconcile,
# assert_listed_teams_have_attributes) still hold against a stale mart, and the lines and
# prediction assertions read a single unchanged source. Tagging those would drop real coverage
# from the every-two-hours DAG for nothing. tests/test_dag_structure.py enforces both
# directions, so the seventh instance fails in CI rather than at 02:00 on a game day.
TEST_EXCLUDE = "--exclude tag:full_refresh_only"

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
    state = schedule_state(now)
    decision = should_refresh_scores(
        now_utc=now,
        config=load_config(),
        hours_since_last_kickoff=state.hours_since_last_kickoff,
        unfinished_recent=state.unfinished_recent,
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
        # `ignore_downstream_trigger_rules=False` SO THE HEARTBEAT CAN TELL THE
        # DIFFERENCE BETWEEN IDLE AND DEAD.
        #
        # With True, a closed gate skips every downstream task no matter what trigger rule
        # it carries — including the heartbeat. The pipeline would then emit nothing all
        # off-season, and a dead-man's switch cannot distinguish "correctly idle" from
        # "the box is off". That is the exact confusion it exists to remove.
        #
        # With False, each downstream task applies its own rule. The work tasks default to
        # all_success and still skip behind a closed gate, unchanged; the heartbeat uses
        # none_failed and therefore beats on a deliberate skip and stays silent on a
        # failure. A skipped gate is a normal outcome, not a failure.
        ignore_downstream_trigger_rules=False,
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

    # The dead-man's switch. Downstream of publish and left at the default all_success
    # trigger rule, so it beats only when the whole chain reached the site.
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
                "scores_refresh",
                dag_id=getattr(c.get("dag_run"), "dag_id", "") or "",
                run_id=getattr(c.get("dag_run"), "run_id", "") or ""),
    )

    gate >> fetch >> load >> dbt_run >> dbt_test >> publish >> beat
