"""Selective rebuild: what a deploy decides to build, and what it decides to ship.

The deploy rebuilt all 95 production models whenever anything under `dbt/models/serving/`
moved — 328 seconds measured on 2026-09-04, for a change that touched one model. It also
MISSED upstream changes entirely, which its own comment recorded and R-127 hit by hand.

Both halves are the same decision made badly, and the tests here are about the decision. The
rule that matters is not "be fast": it is that every way of being uncertain resolves towards
doing MORE work. A slow deploy is an annoyance; a deploy that skipped a model ships a
half-built warehouse and looks exactly like a fast one.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import deploy_models as dm                   # noqa: E402


# --- choosing what to build ---------------------------------------------------------------

def test_every_uncertainty_falls_back_to_rebuilding_everything():
    """THE SAFETY PROPERTY, AND IT IS THE ONLY ONE THAT REALLY MATTERS HERE.

    Enumerated rather than asserted once, because each of these is a different way of not
    knowing what changed and every one of them has to land on the same answer.
    """
    assert dm.choose_selector(full=True, previous=None)[0] == dm.FULL_SELECTOR
    assert dm.choose_selector(full=True, previous=Path("/x/manifest.json"))[0] \
        == dm.FULL_SELECTOR
    assert dm.choose_selector(full=False, previous=None)[0] == dm.FULL_SELECTOR
    # ...and only a real manifest, with no override, narrows it.
    selector, why = dm.choose_selector(full=False, previous=Path("/x/manifest.json"))
    assert selector == dm.CHANGED_SELECTOR
    assert "/x/manifest.json" in why


def test_the_reason_is_always_stated():
    """A deploy that quietly did less than you expected is indistinguishable from one that
    did nothing at all. Every branch says which it took and why."""
    for full in (True, False):
        for previous in (None, Path("/x/manifest.json")):
            _, why = dm.choose_selector(full, previous)
            assert why and why.strip(), (full, previous)


def test_the_narrow_selector_intersects_rather_than_unions():
    """Comma is INTERSECTION in dbt's selector syntax and a space is union. Written with a
    space this would rebuild everything modified PLUS the entire production surface — the
    slow path, arrived at by a typo, with nothing to show it had happened."""
    assert "," in dm.CHANGED_SELECTOR
    assert " " not in dm.CHANGED_SELECTOR
    assert dm.CHANGED_SELECTOR.startswith("state:modified+")
    assert "tag:production" in dm.CHANGED_SELECTOR


def test_a_truncated_manifest_counts_as_no_manifest(tmp_path, monkeypatch):
    """Half a manifest is worse than none: dbt would compare against a partial graph and
    UNDER-select, which is the one outcome the fallback exists to prevent."""
    monkeypatch.setattr(dm, "DEPLOYED_STATE", tmp_path)
    assert dm.previous_manifest() is None, "no file at all"

    (tmp_path / "manifest.json").write_text('{"nodes": {"a": ')
    assert dm.previous_manifest() is None, "truncated JSON"

    (tmp_path / "manifest.json").write_text('{"nodes": {}}')
    assert dm.previous_manifest() == tmp_path / "manifest.json"


def test_the_state_flag_points_at_the_directory_dbt_expects():
    """`--state` takes the DIRECTORY holding manifest.json, not the file. Passing the file
    makes dbt report no previous state and silently select nothing."""
    calls = []

    class _Done:
        returncode, stdout, stderr = 0, "", ""

    import subprocess
    original = subprocess.run
    subprocess.run = lambda cmd, **kw: (calls.append(cmd), _Done())[1]
    try:
        dm.run_dbt(dm.CHANGED_SELECTOR, Path("/state/deployed/manifest.json"))
    finally:
        subprocess.run = original
    assert "--state" in calls[0]
    assert calls[0][calls[0].index("--state") + 1] == "/state/deployed"


# --- choosing what to publish --------------------------------------------------------------

def _artefacts(tmp_path, results, nodes):
    (tmp_path / "run_results.json").write_text(json.dumps({"results": results}))
    (tmp_path / "manifest.json").write_text(json.dumps({"nodes": nodes}))
    return tmp_path / "run_results.json", tmp_path / "manifest.json"


def test_only_serving_models_that_actually_succeeded_are_published(tmp_path):
    """Read from what HAPPENED, not from what was asked for.

    The selector says what dbt was told to build. run_results says what it built. Publishing
    from the first would ship a table that errored as though it had been rebuilt — the site
    would then read a stale relation with no sign anything went wrong.
    """
    results = [
        {"unique_id": "model.cfdb_dbt.srv_game", "status": "success"},
        {"unique_id": "model.cfdb_dbt.srv_game_team", "status": "error"},
        {"unique_id": "model.cfdb_dbt.fct_game", "status": "success"},
        {"unique_id": "test.cfdb_dbt.some_test", "status": "success"},
        {"unique_id": "model.cfdb_dbt.srv_odds_board", "status": "skipped"},
    ]
    nodes = {
        "model.cfdb_dbt.srv_game": {"resource_type": "model", "schema": "serving",
                                    "name": "srv_game"},
        "model.cfdb_dbt.srv_game_team": {"resource_type": "model", "schema": "serving",
                                         "name": "srv_game_team"},
        "model.cfdb_dbt.fct_game": {"resource_type": "model", "schema": "marts",
                                    "name": "fct_game"},
        "test.cfdb_dbt.some_test": {"resource_type": "test", "schema": "serving",
                                    "name": "some_test"},
        "model.cfdb_dbt.srv_odds_board": {"resource_type": "model", "schema": "serving",
                                          "name": "srv_odds_board"},
    }
    assert dm.models_built(*_artefacts(tmp_path, results, nodes)) == ["srv_game"]


def test_a_mart_only_change_publishes_nothing(tmp_path):
    """The site reads the serving layer and nothing else. A rebuilt mart that feeds no
    serving table has nothing to ship — and a serving table that DOES read it is carried into
    the run by the `+`, so it appears here on its own."""
    results = [{"unique_id": "model.cfdb_dbt.fct_game_market", "status": "success"}]
    nodes = {"model.cfdb_dbt.fct_game_market": {"resource_type": "model", "schema": "marts",
                                                "name": "fct_game_market"}}
    assert dm.models_built(*_artefacts(tmp_path, results, nodes)) == []


def test_an_alias_is_respected_over_the_model_name(tmp_path):
    """The published table is named by the relation, not by the file. They agree everywhere
    in this project today, which is exactly why nothing would notice the day they stop."""
    results = [{"unique_id": "model.cfdb_dbt.some_model", "status": "success"}]
    nodes = {"model.cfdb_dbt.some_model": {"resource_type": "model", "schema": "serving",
                                           "name": "some_model", "alias": "srv_renamed"}}
    assert dm.models_built(*_artefacts(tmp_path, results, nodes)) == ["srv_renamed"]


def test_the_target_directory_comes_from_the_environment(monkeypatch):
    """WHERE DBT WRITES IS NOT `<project>/target` ON THE DROPLET, AND ASSUMING IT WAS WOULD
    HAVE PUBLISHED FROM A FIVE-DAY-OLD MANIFEST.

    The container sets DBT_TARGET_PATH to a writable volume. `<project>/target` still exists
    there, holding artefacts from 31 August owned by uid 501 — a macOS uid, left by a laptop
    run before the migration. The first version of this module read that path. It would have
    chosen a plausible set of tables from stale metadata and looked entirely normal doing it.
    """
    import importlib
    monkeypatch.setenv("DBT_TARGET_PATH", "/somewhere/else/target")
    monkeypatch.setenv("CFDB_DBT_PROJECT_DIR", "/proj/dbt")
    reloaded = importlib.reload(dm)
    try:
        assert str(reloaded.TARGET_DIR) == "/somewhere/else/target"
        # And with no env var it falls back to the conventional location rather than guessing.
        monkeypatch.delenv("DBT_TARGET_PATH")
        again = importlib.reload(dm)
        assert str(again.TARGET_DIR) == "/proj/dbt/target"
    finally:
        monkeypatch.undo()
        importlib.reload(dm)


def test_stale_artefacts_are_an_error_rather_than_a_publish(tmp_path, monkeypatch, capsys):
    """The freshness guard. If run_results predates the run we just launched, the module is
    reading the wrong directory — and the wrong directory produces a believable answer."""
    monkeypatch.setattr(dm, "TARGET_DIR", tmp_path)
    monkeypatch.setattr(dm, "DEPLOYED_STATE", tmp_path / "deployed")
    (tmp_path / "run_results.json").write_text('{"results": []}')
    (tmp_path / "manifest.json").write_text('{"nodes": {}}')
    # Both artefacts predate the run by an hour.
    import os as _os
    old = dm.time.time() - 3600
    for name in ("run_results.json", "manifest.json"):
        _os.utime(tmp_path / name, (old, old))

    monkeypatch.setattr(dm, "previous_manifest", lambda: None)

    class _Done:
        returncode, stdout, stderr = 0, "Done. PASS=1", ""

    monkeypatch.setattr(dm, "run_dbt", lambda *a, **k: _Done())
    assert dm.main([]) == 1
    assert "not written by this run" in capsys.readouterr().out
    assert not (tmp_path / "deployed" / "manifest.json").exists(), (
        "a failed run must not be recorded as deployed")


def test_a_failed_publish_does_not_mark_the_change_deployed(tmp_path, monkeypatch):
    """THE ONE THAT WOULD BE INVISIBLE. If the run works and the publish raises, the next
    deploy must still see those models as un-deployed — otherwise one bad publish hides the
    change from every deploy that follows, and the site serves a stale table indefinitely."""
    monkeypatch.setattr(dm, "TARGET_DIR", tmp_path)
    monkeypatch.setattr(dm, "DEPLOYED_STATE", tmp_path / "deployed")
    monkeypatch.setattr(dm, "previous_manifest", lambda: None)

    class _Done:
        returncode, stdout, stderr = 0, "Done. PASS=1", ""

    def fake_run(*_a, **_k):
        # Written BY the run, as real dbt does — otherwise the freshness guard correctly
        # rejects them and this test would pass for the wrong reason.
        (tmp_path / "run_results.json").write_text(json.dumps(
            {"results": [{"unique_id": "model.c.srv_game", "status": "success"}]}))
        (tmp_path / "manifest.json").write_text(json.dumps(
            {"nodes": {"model.c.srv_game": {"resource_type": "model", "schema": "serving",
                                            "name": "srv_game"}}}))
        return _Done()

    monkeypatch.setattr(dm, "run_dbt", fake_run)

    def boom(_tables, _schema):
        raise RuntimeError("transfer failed")

    import src.publish_marts as pm
    monkeypatch.setattr(pm, "publish_schema", boom)
    with pytest.raises(RuntimeError):
        dm.main([])
    assert not (tmp_path / "deployed" / "manifest.json").exists()
