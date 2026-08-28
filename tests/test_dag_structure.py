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
