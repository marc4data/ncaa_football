"""Tests for the CFBD ingestion utility.

No test here touches the network — `requests.get` is always stubbed. CI must not
spend the CFBD rate limit, and the API key never needs to exist for unit tests.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import ingest


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    @property
    def text(self):
        return str(self._payload)


@pytest.fixture
def in_tmp_repo(tmp_path, monkeypatch):
    """Run inside a throwaway cwd so raw files land under tmp_path/data/raw."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ingest, "manifest", ingest.RawManifest(base_dir=Path("data") / "raw"))
    monkeypatch.setattr(ingest, "CFBD_API_KEY", "test-key")
    return tmp_path


def stub_get(monkeypatch, response, captured=None):
    def _get(url, headers=None, params=None, timeout=None):
        if captured is not None:
            captured.update({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return response

    monkeypatch.setattr(ingest.requests, "get", _get)


def test_fetch_writes_raw_file_and_manifest_entry(in_tmp_repo, monkeypatch):
    stub_get(monkeypatch, FakeResponse(200, [{"id": 2000, "school": "Abilene Christian"}]))

    ingest.fetch("teams", {})

    raw_files = [p for p in (in_tmp_repo / "data" / "raw" / "teams").iterdir() if p.name != "manifest.json"]
    assert len(raw_files) == 1

    written = json.loads(raw_files[0].read_text())
    assert written["status_code"] == 200
    assert written["data"][0]["school"] == "Abilene Christian"

    entries = json.loads((in_tmp_repo / "data" / "raw" / "teams" / "manifest.json").read_text())
    assert entries[0]["status_code"] == 200


def test_raw_filename_is_clean_utc_timestamp(in_tmp_repo, monkeypatch):
    """Filenames are manifest keys — no UTC offset, no stray '+', sortable, ms precision."""
    stub_get(monkeypatch, FakeResponse(200, []))

    ingest.fetch("teams", {})

    raw_files = [p for p in (in_tmp_repo / "data" / "raw" / "teams").iterdir() if p.name != "manifest.json"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z\.json", raw_files[0].name)


def test_same_millisecond_writes_do_not_overwrite(in_tmp_repo, monkeypatch):
    """Two responses landing on the same timestamp must produce two distinct files.

    Regression: at second resolution this silently overwrote the earlier file and left it
    labelled with the wrong request's params — 6 files were corrupted this way during the
    first 2024-25 backfill.
    """
    frozen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    class FrozenClock:
        @staticmethod
        def now(tz=None):
            return frozen

    monkeypatch.setattr(ingest, "datetime", FrozenClock)

    first = ingest.write_raw("teams", {"status_code": 200, "params": {"week": "1"}, "data": []})
    second = ingest.write_raw("teams", {"status_code": 200, "params": {"week": "2"}, "data": []})

    assert first != second
    raw_dir = in_tmp_repo / "data" / "raw" / "teams"
    assert (raw_dir / first).exists()
    assert (raw_dir / second).exists()
    # And each file still holds its own request's params.
    assert json.loads((raw_dir / first).read_text())["params"] == {"week": "1"}
    assert json.loads((raw_dir / second).read_text())["params"] == {"week": "2"}


def test_fetch_raises_when_manifest_refuses_the_entry(in_tmp_repo, monkeypatch):
    """Unrecorded provenance is a hard failure, not a warning."""
    stub_get(monkeypatch, FakeResponse(200, []))
    monkeypatch.setattr(ingest.manifest, "add_entry", lambda *a, **k: False)

    with pytest.raises(RuntimeError, match="provenance"):
        ingest.fetch("teams", {})


def test_fetch_sends_bearer_auth_header(in_tmp_repo, monkeypatch):
    captured = {}
    stub_get(monkeypatch, FakeResponse(200, []), captured)

    ingest.fetch("teams", {})

    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["url"] == "https://api.collegefootballdata.com/teams"


def test_fetch_records_error_responses(in_tmp_repo, monkeypatch):
    """A 401 still lands on disk — failures are visible, never swallowed."""
    stub_get(monkeypatch, FakeResponse(401, None))

    ingest.fetch("teams", {})

    entries = json.loads((in_tmp_repo / "data" / "raw" / "teams" / "manifest.json").read_text())
    assert entries[0]["status_code"] == 401


def test_fetch_survives_non_json_response(in_tmp_repo, monkeypatch):
    """An HTML error page must not crash the run."""
    stub_get(monkeypatch, FakeResponse(500, ValueError("not json")))

    ingest.fetch("teams", {})

    raw_files = [p for p in (in_tmp_repo / "data" / "raw" / "teams").iterdir() if p.name != "manifest.json"]
    written = json.loads(raw_files[0].read_text())
    assert written["status_code"] == 500


def test_nested_endpoint_flattens_to_one_directory(in_tmp_repo, monkeypatch):
    stub_get(monkeypatch, FakeResponse(200, []))

    ingest.fetch("games/teams", {"year": "2024"})

    assert (in_tmp_repo / "data" / "raw" / "games_teams").is_dir()


def test_fetch_without_api_key_exits(in_tmp_repo, monkeypatch):
    monkeypatch.setattr(ingest, "CFBD_API_KEY", None)

    with pytest.raises(SystemExit):
        ingest.fetch("teams", {})
