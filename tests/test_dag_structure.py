"""DAG wiring properties that a green run cannot demonstrate.

Airflow is not installed in CI — the DAGs run in the scheduler image, not here — so these
read the source, the same way test_site_foundation asserts on page files it cannot render.
That is a real limitation and worth stating: these pin the SHAPE of the graph, and the
scheduler is what proves it parses. `scripts/deploy_main.sh` runs `dags list-import-errors`
immediately after every deploy, which is where a broken graph actually surfaces.
"""
import re
from pathlib import Path

DAGS = Path(__file__).resolve().parents[1] / "dags"


def _source(name: str) -> str:
    return (DAGS / name).read_text()


def _code(name: str) -> str:
    """Source with comment lines removed.

    The first version of the leaf test asserted on the raw file and failed on the COMMENT
    explaining why the wiring changed, which quotes the very expression it forbids. A test
    that cannot tell prose from code is a test that gets loosened rather than fixed — the
    same trap test_site_foundation hit on the week-floor copy.
    """
    return "\n".join(line for line in _source(name).splitlines()
                     if not line.lstrip().startswith("#"))


def test_publish_is_a_leaf_so_a_skipped_publish_fails_the_run():
    """A DagRun takes its state from its LEAF tasks, and publish is the point of the run.

    While the weekly DAGs ended `publish >> capture_dq`, capture_dq — correctly `all_done`,
    because test history matters most when tests fail — succeeded whether or not publish had
    run. Being the only leaf, it reported the whole run SUCCESS. Every weekly refresh between
    23 and 28 August 2026 was green while publish sat `upstream_failed` behind a red dbt
    test, and the site went five days stale with nothing on the DAG list saying so.
    """
    code = _code("weekly_refresh_dag.py")
    assert "publish >> capture_dq" not in code, (
        "capture_test_results must not be downstream of publish: as an all_done leaf it "
        "would mask a skipped publish and report the run as successful")
    assert "dbt_test >> capture_dq" in code
    assert code.rstrip().rstrip(")").rstrip().endswith(">> publish") or \
        re.search(r">> publish\s*$", code, re.MULTILINE), \
        "publish must terminate its chain, so that it is a leaf"


def test_capture_still_runs_when_tests_fail():
    """The reason capture_dq exists is the failing run, so moving it must not have cost it
    the trigger rule that guarantees it records one."""
    source = _source("weekly_refresh_dag.py")
    assert 'trigger_rule="all_done"' in source


def test_every_dag_that_can_stall_bounds_itself():
    """A task with no execution_timeout ends by scheduler heartbeat timeout, not by a limit
    of its own — which produces no summary and no traceback. The Databricks sync blocked for
    over 17 minutes inside one socket read on 23 August and died exactly that way."""
    assert "execution_timeout" in _source("databricks_sync_dag.py")


def test_the_databricks_client_cannot_outlive_the_heartbeat():
    """The connector's 900s default exceeds Airflow's 300s task-heartbeat timeout, so a
    single stalled statement got the worker killed before `load_endpoints` could use retries
    two and three — the hang disabled the recovery written for it."""
    src = (DAGS.parent / "src" / "load_raw_to_databricks.py").read_text()
    assert "_socket_timeout" in src and "_retry_stop_after_attempts_duration" in src
    # Read from source rather than imported: the module imports `databricks.sql`, which is a
    # runtime dependency of the scheduler image and not of a laptop. A structural assertion
    # should not need the connector installed to run.
    match = re.search(r"^STATEMENT_TIMEOUT_SECONDS\s*=\s*(\d+)", src, re.MULTILINE)
    assert match, "STATEMENT_TIMEOUT_SECONDS must be a module-level literal"
    assert int(match.group(1)) <= 300, (
        "must stay at or under Airflow's 300s task-heartbeat timeout, or a stalled "
        "statement gets the task zombied instead of raising a retryable error")


def test_the_private_connector_api_we_depend_on_is_pinned():
    """`_socket_timeout` and `_retry_stop_after_attempts_duration` are underscore-prefixed
    and carry no stability guarantee. Floating in transitively via dbt-databricks meant a
    rebuild could rename either one and fail every sync at connect()."""
    reqs = (DAGS.parent / "requirements.txt").read_text()
    assert "databricks-sql-connector==" in reqs


# --- the legacy-mart boundary ------------------------------------------------------------

LEGACY_MARTS = ("mart_team_schedule", "mart_team_season_record")

# What cfbd_scores_refresh rebuilds: the five serving views and their ancestors. stg_games is
# the ancestor that actually moves — every completed game changes it — so it stands in for
# the rebuilt side here.
REBUILT = ("stg_games", "srv_scoreboard", "srv_schedule", "srv_matchup",
           "srv_team_game_log", "srv_today_edges", "srv_standings")


TAG_DIRECTIVE = re.compile(r"config\s*\(\s*tags\s*=\s*\[[^\]]*['\"]legacy_mart['\"]")


def _dbt_tests():
    for path in sorted((DAGS.parent / "dbt" / "tests").glob("*.sql")):
        yield path, path.read_text()


def _is_tagged(src: str) -> bool:
    """Match the dbt config DIRECTIVE, not the word.

    The first version tested `"legacy_mart" in src` and passed on a file whose config line
    had been deleted, because the comment explaining the tag still mentions it by name. That
    is the third time in this repo a source-reading test has matched its own prose — the
    week-floor copy test and the publish-leaf test both did it first.
    """
    return bool(TAG_DIRECTIVE.search(src))


def test_every_test_crossing_the_legacy_mart_boundary_is_tagged():
    """The rule is CROSSING the boundary, not touching a mart.

    A test comparing a legacy mart against a model cfbd_scores_refresh rebuilds is measuring
    how long it has been since the last full build, because that DAG refreshes one side and
    never the other. Four separate outages in the week of 24 August were this same defect
    wearing a different test name each time, tagged one at a time as each surfaced. This
    fails on the fifth rather than waiting for it to block another game day.
    """
    untagged = []
    for path, src in _dbt_tests():
        refs = re.findall(r"ref\('([a-z_0-9]+)'\)", src)
        crosses = (any(r in LEGACY_MARTS for r in refs)
                   and any(r in REBUILT for r in refs))
        if crosses and not _is_tagged(src):
            untagged.append(path.name)
    assert not untagged, (
        "these compare a legacy mart against a model cfbd_scores_refresh rebuilds and must "
        f"carry {{{{ config(tags=['legacy_mart']) }}}}: {untagged}")


def test_mart_only_invariants_keep_their_coverage_in_the_scores_dag():
    """The exclusion must stay narrow. A test that reads ONLY a legacy mart still holds when
    that mart is stale — it was internally consistent when built — so tagging it would drop
    real coverage from the every-two-hours DAG to no purpose."""
    over_tagged = []
    for path, src in _dbt_tests():
        refs = set(re.findall(r"ref\('([a-z_0-9]+)'\)", src))
        if _is_tagged(src) and not (refs & set(REBUILT)):
            over_tagged.append(path.name)
    assert not over_tagged, (
        f"these read no rebuilt model, so the tag costs coverage for nothing: {over_tagged}")


def test_the_scores_dag_excludes_the_tag_it_relies_on():
    assert "--exclude tag:legacy_mart" in _code("scores_refresh_dag.py")
