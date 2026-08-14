"""Tests for the raw manifest — the record of what we pulled and when.

The manifest backs data quality rule #2 (idempotent loads): re-running a fetch
must never create a duplicate entry for the same raw file.
"""
import json
from datetime import datetime

from src.raw_manifest import RawManifest


def test_add_entry_creates_manifest(tmp_path):
    m = RawManifest(base_dir=tmp_path)

    assert m.add_entry("teams", "2026-01-01T00-00-00.json", {}, 200) is True

    manifest_file = tmp_path / "teams" / "manifest.json"
    assert manifest_file.exists()
    entries = json.loads(manifest_file.read_text())
    assert len(entries) == 1
    assert entries[0]["filename"] == "2026-01-01T00-00-00.json"
    assert entries[0]["status_code"] == 200


def test_add_entry_is_idempotent_on_filename(tmp_path):
    """Re-adding the same filename is refused — no duplicate rows."""
    m = RawManifest(base_dir=tmp_path)
    m.add_entry("teams", "dup.json", {}, 200)

    assert m.add_entry("teams", "dup.json", {}, 200) is False
    assert len(m.list_entries("teams")) == 1


def test_added_at_is_timezone_aware_utc(tmp_path):
    """Guards the utcnow() fix: naive timestamps can't prove they're UTC."""
    m = RawManifest(base_dir=tmp_path)
    m.add_entry("teams", "tz.json", {}, 200)

    added_at = m.list_entries("teams")[0]["added_at"]
    parsed = datetime.fromisoformat(added_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_failed_fetches_are_recorded_not_swallowed(tmp_path):
    """A 401/500 must leave a trace — silent failure violates data quality rule #5."""
    m = RawManifest(base_dir=tmp_path)
    m.add_entry("teams", "failed.json", {}, 401)

    assert m.list_entries("teams")[0]["status_code"] == 401


def test_exists_matches_on_params(tmp_path):
    m = RawManifest(base_dir=tmp_path)
    m.add_entry("games", "g.json", {"year": "2024"}, 200)

    assert m.exists("games", {"year": "2024"}) is True
    assert m.exists("games", {"year": "2025"}) is False


def test_list_entries_on_missing_endpoint_is_empty(tmp_path):
    assert RawManifest(base_dir=tmp_path).list_entries("never-fetched") == []
