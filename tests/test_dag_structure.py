"""DAG wiring properties that a green run cannot demonstrate.

Airflow is not installed in CI — the DAGs run in the scheduler image, not here — so these
read the source, the same way test_site_foundation asserts on page files it cannot render.
That is a real limitation and worth stating: these pin the SHAPE of the graph, and the
scheduler is what proves it parses. `scripts/deploy_main.sh` runs `dags list-import-errors`
immediately after every deploy, which is where a broken graph actually surfaces.
"""
import re

import pytest
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

    # THE PROPERTY IS "A FAILED PUBLISH FAILS THE RUN", NOT "PUBLISH IS LITERALLY THE LEAF".
    #
    # The dead-man's switch put a heartbeat downstream of publish, so publish stopped being
    # the terminal task and this assertion — written as "the chain ends at publish" — failed.
    # It was right to fail: the mechanism changed. But the guarantee survives, and by the
    # same route it always relied on. `beat` uses the DEFAULT all_success rule here, so a
    # failed or upstream-failed publish leaves the heartbeat upstream_failed, and an
    # upstream_failed leaf fails the DagRun exactly as a failed publish leaf did.
    #
    # What must never happen again is the chain ending in a task that succeeds regardless —
    # which is what capture_dq's all_done did. So the test now checks the terminal task is
    # the heartbeat and that the weekly heartbeat carries no permissive trigger rule,
    # rather than checking a task position that legitimately moved.
    assert re.search(r">> publish >> beat\s*$", code, re.MULTILINE), (
        "publish must be followed only by the heartbeat, which terminates the chain")
    assert "TriggerRule" not in code, (
        "the weekly heartbeat must keep the strict all_success default: a permissive rule "
        "would let the terminal task succeed behind a failed publish, which is the exact "
        "masking capture_dq used to do")


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
# THE LISTS THAT USED TO LIVE HERE ARE GONE, AND WHY THEY WENT IS THE POINT.
#
# `GAME_DERIVED` and `LEGACY_MARTS` were hardcoded names, and the test below said of itself:
# "This fails on the seventh in CI instead." IT DID NOT. On 2026-09-04
# `assert_team_series_reconciles` became the seventh and slipped straight through, because it
# compares `fct_team_series` — a name nobody had added to a two-entry LEGACY_MARTS tuple —
# against `srv_game`. The guard against forgetting needed to be remembered.
#
# (`GAME_DERIVED` also listed "srv_game" four times, the same bulk-rename residue R-192 found
# in SCORES_SELECTOR. A list nobody reads is a list nobody maintains.)
#
# The sides are computed from the compiled dependency graph now: whatever
# `+srv_game +srv_team_game_log +srv_game_weather` actually pulls is refreshed, and everything
# else is not. `ci/check_test_refresh_scope.py` owns that computation and CI runs it; these
# two tests are the pytest face of it.

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


def _manifest_is_stale() -> bool:
    """Is the compiled manifest older than the dbt sources it describes?

    THE GUARD READS AN ARTIFACT, AND AN ARTIFACT CAN LIE BY BEING OLD. Removing the
    `full_refresh_only` tag from a .sql file left every test green here, because the manifest
    still carried the tag from an earlier compile. CI compiles fresh so it is right there; a
    developer editing a test locally would have been told nothing.

    Cheaper than recompiling in a unit test, and it converts a silent pass into a skip that
    says why.
    """
    root = Path(__file__).resolve().parents[1]
    manifest = root / "dbt" / "target" / "manifest.json"
    newest = max((f.stat().st_mtime for f in (root / "dbt").rglob("*.sql")), default=0)
    newest = max(newest, (root / "dbt" / "dbt_project.yml").stat().st_mtime)
    return manifest.stat().st_mtime < newest


def _scope_checker():
    """`ci/check_test_refresh_scope.py`, or None if there is no usable compiled manifest."""
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    if not (root / "dbt" / "target" / "manifest.json").exists():
        return None
    if _manifest_is_stale():
        return None
    spec = importlib.util.spec_from_file_location(
        "check_test_refresh_scope", root / "ci" / "check_test_refresh_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest():
    import json
    return json.loads(
        (Path(__file__).resolve().parents[1] / "dbt" / "target" / "manifest.json").read_text())


def test_every_test_the_scores_dag_cannot_satisfy_is_tagged():
    """The general rule, computed from the graph rather than from a list of names.

    A test comparing something cfbd_scores_refresh refreshes against something it does not is
    measuring the gap between two fetch times. Six were tagged one at a time across the week
    of 24 August, each looking like a separate bug — and the list-based version of this test,
    written to catch the seventh, missed it.
    """
    module = _scope_checker()
    if module is None:
        pytest.skip("no compiled manifest, or it is older than the dbt sources — "
                    "run `dbt compile` so this checks the current project")
    found = module.straddling_tests(_manifest())
    assert not found, [
        f"{name}: {[i.split('.')[-1] for i in inside]} refreshed vs "
        f"{[o.split('.')[-1] for o in outside]} not" for name, inside, outside in found]


def test_single_sided_tests_keep_their_coverage_in_the_scores_dag():
    """The exclusion must stay narrow. A test reading only one side still holds when that side
    is stale — it was internally consistent when built — so tagging it would drop real
    coverage from the every-two-hours DAG to no purpose.

    Also computed from the graph. A tag is justified when the test's relations genuinely span
    the refresh boundary; anything else is coverage given away.
    """
    module = _scope_checker()
    if module is None:
        pytest.skip("no compiled manifest, or it is older than the dbt sources — "
                    "run `dbt compile` so this checks the current project")
    manifest = _manifest()

    refreshed = set()
    for node in module.GATED_SELECTION:
        refreshed.add(node)
        refreshed |= module._ancestors(manifest, node)

    over_tagged = []
    for node in manifest["nodes"].values():
        if node.get("resource_type") != "test":
            continue
        tags = node.get("config", {}).get("tags", [])
        if module.EXEMPT_TAG not in tags:
            continue
        refs = {d for d in node.get("depends_on", {}).get("nodes", [])
                if d.startswith(("model.", "source."))}
        # A TAG ON A TEST THE DAG NEVER SELECTS COSTS NOTHING, so it is not over-tagging.
        # `assert_parity_srv_standings` reads mart_team_season_record and srv_standings and
        # the scores DAG rebuilds NEITHER, so it is never in that run's selection at all. The
        # old list-based version called it over-tagged because its GAME_DERIVED tuple wrongly
        # listed srv_standings as game-derived — `+srv_game` pulls ANCESTORS, and srv_standings
        # is a sibling.
        #
        # Coverage can only be given away where there was coverage: the test must be selected
        # (at least one refreshed relation) and yet not straddle.
        if not refs & refreshed:
            continue
        if not refs - refreshed:
            over_tagged.append(node.get("name"))
    assert not over_tagged, (
        f"these are selected by the scores DAG and do not straddle the boundary, so the tag "
        f"costs real coverage: {sorted(over_tagged)}")


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


# --- the warehouse is the product, so the warehouse gets refreshed ------------------------

def test_the_weekly_refresh_builds_staging_even_with_no_serving_consumer():
    """`+tag:production` pulls the serving layer and its ancestors, so a staging model
    reached the scheduled refresh only by being upstream of something the site renders.

    That was right when the site was the product. Prompt 029 makes the warehouse itself the
    deliverable, and the whole of Priority 3 is staging models for endpoints no page reads —
    under the old rule every one of them would exist in git, pass CI, and never materialise.
    stg_game_weather and stg_game_player_stat shipped and neither was selected.
    """
    source = (DAGS / "weekly_refresh_dag.py").read_text()
    code = "\n".join(ln for ln in source.splitlines() if not ln.lstrip().startswith("#"))
    assert "tag:warehouse" in code, (
        "the weekly refresh must select tag:warehouse, or staging models with no serving "
        "consumer are never built")
    assert "+tag:production" in code, "the site's surface still has to be refreshed"


def test_the_scores_refresh_stays_narrow():
    """The two-hourly DAG rebuilds what the live site needs and nothing else. Widening it to
    the warehouse tag would rebuild 1.27M player-stat rows every two hours to no purpose —
    box scores are immutable once the week completes."""
    source = (DAGS / "scores_refresh_dag.py").read_text()
    code = "\n".join(ln for ln in source.splitlines() if not ln.lstrip().startswith("#"))
    assert "tag:warehouse" not in code
    assert "srv_game" in code


def test_the_catalogue_models_get_a_pass_of_their_own_after_everything_else():
    """srv_data_dictionary and srv_system_health describe the database rather than reading
    it, and dbt cannot see that dependency.

    Both read dim_field_metadata, which reads live table and column COMMENTS — written by
    persist_docs at the moment each model is built. Neither declares a ref on the models it
    catalogues, because the dependency is on other models' side effects, not on their rows.
    So dbt schedules them anywhere in the run.

    Measured, on the build that documented the serving layer: srv_system_health reported
    "93 of 634 columns documented" straight after a run that had just written all 634. It
    had been built while its siblings were still going in.

    srv_data_dictionary's header had assumed the DAG solved this by building serving last.
    It cannot: both catalogue models ARE serving models, so "serving last" still puts them
    in the same pass as the models they describe. This pins the actual remedy.
    """
    src = _code("weekly_refresh_dag.py")
    assert "dbt_catalogue" in src, (
        "the catalogue models need a rebuild after the main run, or the dictionary and the "
        "system health board are permanently one build stale")
    # Ordering is the whole point: after the build that writes the comments, and before the
    # tests that read them.
    wiring = re.search(r"dbt_run\s*>>\s*(\w+)\s*>>\s*dbt_test", src)
    assert wiring and wiring.group(1) == "dbt_catalogue", (
        f"expected dbt_run >> dbt_catalogue >> dbt_test, found {wiring and wiring.group(0)!r}")
    # It must stay narrow. Re-running the production selector here would double the build.
    task = src[src.index("dbt_catalogue = BashOperator"):]
    task = task[:task.index(")\n        dbt_test")]
    assert "PRODUCTION_SELECTOR" not in task, (
        "the second pass rebuilds two small tables; running the full selector again would "
        "double the run time to refresh a catalogue")
    for model in ("srv_data_dictionary", "srv_system_health"):
        assert model in task, f"{model} must be in the second pass"


def test_weather_refreshes_on_the_lines_cadence_without_gating_its_heartbeat():
    """Weather is a SIBLING of the lines chain, not a link in it.

    Two separate reasons, and both matter. A weather failure must not stop a lines snapshot:
    the market at 14:00 cannot be observed again at 18:00, so a missed one is gone for good.
    And it must not silence the heartbeat, because that switch monitors the LINES cadence —
    a stale-lines alarm raised by a broken weather endpoint sends someone looking in exactly
    the wrong place.

    The failure is still loud: `weather` is a leaf, so a failure fails the DAG run and fires
    on_failure_callback. Visible, just not conflated.
    """
    src = _code("lines_snapshot_dag.py")
    assert "refresh_weather" in src, "weather must ride the lines cadence"
    # Downstream of the gate, so it is skipped out of season like everything else here.
    assert re.search(r"gate\s*>>\s*weather", src), (
        "weather must sit behind the cadence gate, or it would fetch all off-season")
    # NOT in the chain that feeds the heartbeat.
    assert not re.search(r"weather\s*>>\s*beat", src), (
        "a weather failure must not silence the lines dead-man's switch")
    assert re.search(r"gate\s*>>\s*snapshot\s*>>\s*load\s*>>\s*beat", src), (
        "the lines chain itself must be unchanged")


def test_the_scores_dag_builds_the_weather_model_it_does_not_fetch():
    """Fetch and build live in different DAGs here, exactly as they do for lines: the lines
    DAG lands raw four-hourly, and the scores DAG runs dbt and publishes two-hourly.

    Refreshing raw weather every four hours while rebuilding the model weekly would leave the
    page showing a forecast up to seven days stale on top of current data — which is worse
    than not collecting it, because it looks fresh.
    """
    src = _code("scores_refresh_dag.py")
    assert "+srv_game_weather" in src, (
        "the DAG that runs dbt must rebuild the weather model, or the fetch is wasted")


def test_a_slow_sweep_is_excluded_for_cost_and_says_so():
    """`slow_sweep` exists so `full_refresh_only` keeps meaning one thing.

    The two exclusions answer different questions. full_refresh_only is about CORRECTNESS —
    a test the scores DAG cannot satisfy because it compares refreshed data against stale
    data. slow_sweep is about COST — a test that would be perfectly valid every two hours and
    simply is not worth minutes there.

    Collapsing them would make test_single_sided_tests_keep_their_coverage_in_the_scores_dag
    unenforceable, because a tag that means two things cannot be checked for either.
    """
    src = _code("scores_refresh_dag.py")
    assert "tag:slow_sweep" in src, (
        "the two-hourly DAG must exclude the slow sweeps, or it stops being cheap")
    assert "tag:full_refresh_only" in src, (
        "excluding one reason must not drop the other")

    # And nothing may wear both: that would be a claim that it is simultaneously
    # unsatisfiable here and merely expensive here.
    #
    # Read from the config DIRECTIVE, not from the file text. The first version of this
    # assertion substring-matched the source and failed on the very sweep it was written for,
    # whose comment explains at length why it is NOT full_refresh_only. That is the fourth
    # time a source-reading test in this file has matched its own prose; _is_tagged carries
    # the first three.
    for path, test_src in _dbt_tests():
        config = re.search(r"config\(\s*tags\s*=\s*\[([^\]]*)\]", test_src)
        tags = set(re.findall(r"'([a-z_]+)'", config.group(1))) if config else set()
        assert not {"slow_sweep", "full_refresh_only"} <= tags, (
            f"{path.name} claims both exclusion reasons; they are different claims")


# === the lines DAG grew a transform chain =================================================

def _lines_dag_source():
    return (Path(__file__).resolve().parents[1] / "dags" / "lines_snapshot_dag.py").read_text()


def test_the_distributions_are_built_on_the_lines_cadence_not_the_scores_one():
    """A DISTRIBUTION IS A FUNCTION OF LINES, NOT OF RESULTS.

    `cfbd_scores_refresh` already runs the exact chain these models need — dbt run, dbt test,
    publish serving — every two hours, so the machinery was never missing. Its GATE is the
    mismatch: it asks whether games are SETTLING, and lines move on a Tuesday when nothing is
    settling at all. Widening that gate would spend exactly what it was built to save.
    """
    lines = _lines_dag_source()
    scores = (Path(__file__).resolve().parents[1] / "dags" / "scores_refresh_dag.py").read_text()
    assert "srv_week_metric_distribution" in lines
    assert "srv_week_metric_distribution" not in scores, (
        "the distributions must not also be built on the two-hourly scores cadence — two "
        "DAGs building one model is two answers to when it is current")


def test_the_transform_never_blocks_a_lines_snapshot():
    """THE FETCH IS THE IRREVERSIBLE PART OF THIS DAG. The market at 14:00 cannot be observed
    again at 18:00, so nothing may sit between the gate and the snapshot — and a dbt failure
    least of all.

    Asserted on the dependency line: the transform hangs off `load`, downstream of the
    snapshot, and the snapshot chain does not wait for it.
    """
    source = _lines_dag_source()
    assert "gate >> snapshot >> load >> beat" in source, (
        "the lines chain must remain a straight line from gate to heartbeat")
    assert "[load, weather] >> dbt_distribution" in source
    # ...and nothing downstream of dbt is upstream of the snapshot or the heartbeat.
    assert "dbt_distribution >> snapshot" not in source
    assert "publish_distribution >> beat" not in source


def test_the_heartbeat_still_watches_only_the_lines_chain():
    """The switch monitors the LINES cadence specifically. A stale-lines alarm raised by a
    broken dbt model would send someone looking in the wrong place — the same reasoning that
    already keeps `weather` off the heartbeat's path."""
    source = _lines_dag_source()
    beat_line = next(line for line in source.splitlines()
                     if line.strip().startswith("gate >> snapshot >> load >> beat"))
    assert "dbt" not in beat_line and "publish" not in beat_line


def test_the_selector_pulls_ancestors_and_not_the_whole_project():
    """A four-hourly job has no business rebuilding 53 models. `+` pulls what the two serving
    views need — the facts, the shared value model and the market mart — and nothing else."""
    source = _lines_dag_source()
    assert "+srv_week_metric_distribution" in source
    assert "tag:production" not in source
    assert "--select" in source


def test_both_dbt_dags_name_the_project_directory_the_same_way():
    """Two spellings of one location is how a deploy breaks on one DAG and not the other."""
    import re
    paths = set()
    for name in ("lines_snapshot_dag.py", "scores_refresh_dag.py"):
        text = (Path(__file__).resolve().parents[1] / "dags" / name).read_text()
        found = re.search(r'DBT_PROJECT_DIR = "([^"]+)"', text)
        assert found, name
        paths.add(found.group(1))
    assert len(paths) == 1, paths


def test_the_distribution_publish_ships_the_hot_set_only():
    """The heavy player tables are 608 MB of the serving schema and this link is the
    pipeline's failure point — 59 MB has taken 17 minutes when it is busy. A four-hourly job
    must not put 182 MB on it."""
    source = _lines_dag_source()
    assert 'publish_all(schemas=["serving"], hot=True)' in source
    assert "hot=False" not in source


def test_no_test_straddles_the_gated_dags_refresh_boundary():
    """R-226. THE SEVENTH INSTANCE BLOCKED THE SITE FOR EIGHT HOURS.

    `publish_to_serving` is downstream of `dbt_test` on the default all_success rule, so a
    test that fails for a reason the DAG cannot fix does not merely report a false problem —
    it stops the serving database being updated at all. On 2026-09-04
    `assert_team_series_reconciles` failed on three consecutive runs and the site was only
    fresh because a deploy happened to publish by hand. A November Saturday settles ~298
    games, which would have failed all twelve runs.

    Six of these were tagged one at a time across the week of 24 August, each looking like a
    separate bug. The check reads the compiled manifest; this is the pytest wrapper so a
    developer meets it before CI does.
    """
    import importlib.util
    import json
    root = Path(__file__).resolve().parents[1]
    manifest = root / "dbt" / "target" / "manifest.json"
    if not manifest.exists() or _manifest_is_stale():
        pytest.skip("no compiled manifest, or it is older than the dbt sources")

    spec = importlib.util.spec_from_file_location(
        "check_test_refresh_scope", root / "ci" / "check_test_refresh_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    data = json.loads(manifest.read_text())
    tests = [n for n in data["nodes"].values() if n.get("resource_type") == "test"]
    assert len(tests) >= 50, f"only {len(tests)} tests — the manifest is not being read"

    found = module.straddling_tests(data)
    assert not found, [
        f"{name}: {[i.split('.')[-1] for i in inside]} (refreshed) vs "
        f"{[o.split('.')[-1] for o in outside]} (not)" for name, inside, outside in found]


def test_the_straddle_check_catches_every_instance_that_has_actually_happened():
    """A GUARD THAT HAS NEVER FAILED IS NOT EVIDENCE, and the first version of this one caught
    two of six — it required the word "join", which excluded a comparison against a raw source
    and one that compares without the keyword.

    Each of the six is untagged in turn and the check must find it. It must also stay silent
    on the sweeps, which read 8 to 80 relations and check each independently: a stale
    `fct_team_rating` cannot make `fct_game`'s uniqueness fail, and those have run in the gated
    DAG for weeks without trouble.
    """
    import importlib.util
    import json
    root = Path(__file__).resolve().parents[1]
    manifest = root / "dbt" / "target" / "manifest.json"
    if not manifest.exists() or _manifest_is_stale():
        pytest.skip("no compiled manifest, or it is older than the dbt sources")
    spec = importlib.util.spec_from_file_location(
        "check_test_refresh_scope", root / "ci" / "check_test_refresh_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    known = ["assert_team_series_reconciles",
             "assert_derived_record_matches_cfbd_records",
             "assert_games_played_reconciles_to_schedule",
             "assert_date_only_seasons_are_not_timezone_shifted"]
    for target in known:
        data = json.loads(manifest.read_text())
        present = False
        for node in data["nodes"].values():
            if node.get("name") == target:
                node["config"]["tags"] = []
                present = True
        if not present:
            continue
        names = [n for n, _, _ in module.straddling_tests(data)]
        assert target in names, f"{target} would slip through untagged"

    # The sweeps must NOT be flagged, or a 4-in-5 false-positive rate gets the check switched
    # off and the class goes unguarded again.
    data = json.loads(manifest.read_text())
    names = [n for n, _, _ in module.straddling_tests(data)]
    for sweep in ("assert_facts_are_unique_on_their_natural_key",
                  "assert_staging_models_are_unique_on_their_grain",
                  "assert_every_serving_row_names_its_team"):
        assert sweep not in names, f"{sweep} is a sweep, not a comparison"
