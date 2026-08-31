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


# --- what cfbd_scores_refresh cannot satisfy ------------------------------------------------

# cfbd_scores_refresh fetches /games and rebuilds the five serving views plus ancestors.
# Anything else in the warehouse is whatever the last full refresh left behind.
GAME_DERIVED = ("stg_games", "fct_game", "fct_game_team", "fct_team_record",
                "srv_scoreboard", "srv_schedule", "srv_matchup", "srv_team_game_log",
                "srv_today_edges", "srv_standings")
LEGACY_MARTS = ("mart_team_schedule", "mart_team_season_record")

TAG_DIRECTIVE = re.compile(r"config\s*\(\s*tags\s*=\s*\[[^\]]*['\"]full_refresh_only['\"]")


def _dbt_tests():
    for path in sorted((DAGS.parent / "dbt" / "tests").glob("*.sql")):
        yield path, path.read_text()


def _is_tagged(src: str) -> bool:
    """Match the dbt config DIRECTIVE, not the word.

    An earlier version tested `"full_refresh_only" in src` and passed on a file whose config
    line had been deleted, because the comment explaining the tag still names it. That is the
    third time a source-reading test here has matched its own prose — the week-floor copy test
    and the publish-leaf test both did it first.
    """
    return bool(TAG_DIRECTIVE.search(src))


def _sides(src: str):
    """(refreshed_by_scores, not_refreshed_by_scores) — what this test compares."""
    refs = set(re.findall(r"ref\('([a-z_0-9]+)'\)", src))
    sources = set(re.findall(r"source\(\s*'raw'\s*,\s*'([a-z_0-9]+)'\s*\)", src))
    fresh = refs & set(GAME_DERIVED)
    stale = (refs & set(LEGACY_MARTS)) | {s for s in sources if s != "games"}
    return fresh, stale


def test_every_test_the_scores_dag_cannot_satisfy_is_tagged():
    """The general rule, not the six instances.

    A test comparing something cfbd_scores_refresh refreshes against something it does not is
    measuring the gap between two fetch times. Two shapes qualify: a legacy mart that is not
    an ancestor of the five views, and a raw endpoint other than /games that this DAG never
    refetches. Six tests matched; five of them surfaced one at a time across a single week,
    each looking like a separate bug. This fails on the seventh in CI instead.
    """
    untagged = []
    for path, src in _dbt_tests():
        fresh, stale = _sides(src)
        if fresh and stale and not _is_tagged(src):
            untagged.append((path.name, sorted(fresh), sorted(stale)))
    assert not untagged, (
        "these compare refreshed against un-refreshed data and must carry "
        f"{{{{ config(tags=['full_refresh_only']) }}}}: {untagged}")


def test_single_sided_tests_keep_their_coverage_in_the_scores_dag():
    """The exclusion must stay narrow. A test reading only one side still holds when that side
    is stale — it was internally consistent when built — so tagging it would drop real
    coverage from the every-two-hours DAG to no purpose."""
    over_tagged = []
    for path, src in _dbt_tests():
        fresh, stale = _sides(src)
        if _is_tagged(src) and not (fresh and stale):
            over_tagged.append(path.name)
    assert not over_tagged, (
        f"these do not straddle the boundary, so the tag costs coverage for nothing: {over_tagged}")


def test_the_scores_dag_excludes_the_tag_it_relies_on():
    assert "--exclude tag:full_refresh_only" in _code("scores_refresh_dag.py")


# --- one deploy path, one meaning ---------------------------------------------------------

DEPLOY_SCRIPT = DAGS.parent / "scripts" / "deploy_main.sh"


def test_the_deploy_script_targets_the_droplet_not_the_laptop():
    """"Deployed" used to mean three things and merging to main updated one of them.

    The DAGs came from a git worktree on the laptop, the droplet's site was a file copy with
    no git, and the forced command was an scp. On 30 August the cache-TTL fix was on main and
    not on the droplet, and a diff comparing only the files present in both places reported
    no difference while two existed on one side alone. The site was down for a day.

    Since the migration, production is the droplet. Refreshing the laptop worktree here would
    quietly recreate the two-productions problem — it is the M3 rollback, paused, and
    decommissioned when M3 closes.
    """
    code = "\n".join(ln for ln in DEPLOY_SCRIPT.read_text().splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "/opt/cfdb-pipeline/repo" in code or "PIPELINE_DIR" in code
    assert "cfdb_deploy" not in code, (
        "the laptop worktree is the paused rollback, not a deploy target")


def test_the_deploy_script_deploys_the_site_too():
    """The site is a separate image with separate failure modes. A deploy that moves the
    pipeline and leaves the site behind is the gap that caused the outage."""
    code = "\n".join(ln for ln in DEPLOY_SCRIPT.read_text().splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "/opt/cfdb/site" in code or "SITE_DIR" in code
    assert "docker compose build site" in code


def test_the_deploy_script_verifies_the_site_renders():
    """CLAUDE.md, 2026-08-31: the site's definition of done is that the site works. A deploy
    that ends at 'files copied' is the claim that was wrong three times."""
    code = "\n".join(ln for ln in DEPLOY_SCRIPT.read_text().splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "site_smoke.py" in code
    assert "_stcore/health" in code
    assert "fail " in code, "a failed verification must stop the deploy, not just print"


def test_the_deploy_script_disables_applefile_companions_when_syncing():
    """macOS tar emits `._*` files that match the raw loader's *.json glob. 1,772 of them
    came across during the migration and had to be deleted before anything would parse."""
    code = "\n".join(ln for ln in DEPLOY_SCRIPT.read_text().splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "COPYFILE_DISABLE=1" in code
