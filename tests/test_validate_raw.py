"""Tests for the raw-layer audit.

The audit is the safety net for the manifest/file drift that corrupted 6 files during the
first backfill, so its detection needs to be provably right.
"""
import json

from src import validate_raw


def write_raw_file(endpoint_dir, filename, params):
    (endpoint_dir / filename).write_text(json.dumps({
        "status_code": 200, "params": params, "data": [],
    }))


def write_manifest(endpoint_dir, entries):
    (endpoint_dir / "manifest.json").write_text(json.dumps(entries))


def make_endpoint(tmp_path, name="games_teams"):
    d = tmp_path / name
    d.mkdir(parents=True)
    return d


def test_clean_raw_layer_reports_nothing(tmp_path):
    d = make_endpoint(tmp_path)
    write_raw_file(d, "a.json", {"week": "1"})
    write_manifest(d, [{"filename": "a.json", "params": {"week": "1"}, "status_code": 200}])

    assert validate_raw.audit(tmp_path) == ([], [], [])


def test_detects_mismatched_params(tmp_path):
    """The dangerous case: file holds a different request's response than the manifest says."""
    d = make_endpoint(tmp_path)
    write_raw_file(d, "a.json", {"week": "5"})
    write_manifest(d, [{"filename": "a.json", "params": {"week": "4"}, "status_code": 200}])

    mismatched, missing, orphans = validate_raw.audit(tmp_path)
    assert len(mismatched) == 1
    assert "week" in mismatched[0]
    assert (missing, orphans) == ([], [])


def test_detects_missing_file(tmp_path):
    d = make_endpoint(tmp_path)
    write_manifest(d, [{"filename": "gone.json", "params": {}, "status_code": 200}])

    mismatched, missing, orphans = validate_raw.audit(tmp_path)
    assert missing == ["games_teams/gone.json"]
    assert (mismatched, orphans) == ([], [])


def test_detects_orphan_file(tmp_path):
    d = make_endpoint(tmp_path)
    write_raw_file(d, "unclaimed.json", {"week": "1"})
    write_manifest(d, [])

    mismatched, missing, orphans = validate_raw.audit(tmp_path)
    assert orphans == ["games_teams/unclaimed.json"]
    assert (mismatched, missing) == ([], [])


def test_repair_removes_file_and_manifest_entry(tmp_path):
    d = make_endpoint(tmp_path)
    write_raw_file(d, "bad.json", {"week": "5"})
    write_raw_file(d, "good.json", {"week": "9"})
    write_manifest(d, [
        {"filename": "bad.json", "params": {"week": "4"}, "status_code": 200},
        {"filename": "good.json", "params": {"week": "9"}, "status_code": 200},
    ])

    mismatched, _, _ = validate_raw.audit(tmp_path)
    removed = validate_raw.repair(mismatched, tmp_path)

    assert removed == 1
    assert not (d / "bad.json").exists()
    assert (d / "good.json").exists()
    remaining = json.loads((d / "manifest.json").read_text())
    assert [e["filename"] for e in remaining] == ["good.json"]
    # And the layer is clean afterwards, so a backfill rerun refetches the gap.
    assert validate_raw.audit(tmp_path) == ([], [], [])


def test_missing_raw_root_is_not_an_error(tmp_path):
    assert validate_raw.audit(tmp_path / "nonexistent") == ([], [], [])
