"""Tests for the Databricks sync's decision logic.

The loading itself needs a warehouse. What is worth pinning down without one is the
question the daily sync asks before it opens a single connection: *which endpoints owe
files?* Getting that wrong is expensive in both directions — too eager and every run pays
64 serverless cold starts, too lazy and files silently never arrive.
"""
from types import SimpleNamespace

import pytest

from src import load_raw_to_databricks as loader


class FakeCursor:
    """Minimal stand-in: returns manifest rows, or raises to model a missing table."""

    def __init__(self, rows=None, raises=False):
        self._rows = rows or []
        self._raises = raises

    def execute(self, _sql):
        if self._raises:
            raise RuntimeError("Table or view not found: raw_manifest")

    def fetchall(self):
        return [SimpleNamespace(endpoint=e, filename=f) for e, f in self._rows]


@pytest.fixture
def raw_layer(tmp_path, monkeypatch):
    """A raw tree with two endpoints, so `pending` has something real to read."""
    for endpoint, names in (("lines", ["a.json", "b.json"]), ("games", ["c.json"])):
        directory = tmp_path / "data" / "raw" / endpoint
        directory.mkdir(parents=True)
        for name in names:
            (directory / name).write_text('{"data": []}', encoding="utf-8")
        # Never an endpoint's own file, and it must not be counted as one.
        (directory / "manifest.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_nothing_pending_when_databricks_has_every_file(raw_layer):
    cursor = FakeCursor([("lines", "a.json"), ("lines", "b.json"), ("games", "c.json")])
    assert loader.pending_by_endpoint(cursor, ["lines", "games"]) == {}


def test_counts_only_the_missing_files(raw_layer):
    cursor = FakeCursor([("lines", "a.json")])
    assert loader.pending_by_endpoint(cursor, ["lines", "games"]) == {"lines": 1, "games": 1}


def test_a_missing_manifest_makes_everything_pending(raw_layer):
    """The first sync ever, before the manifest table exists.

    Fail-safe direction on purpose: assuming nothing is pending would skip the very first
    load and leave Databricks permanently empty with a green task.
    """
    cursor = FakeCursor(raises=True)
    assert loader.pending_by_endpoint(cursor, ["lines", "games"]) == {"lines": 2, "games": 1}


def test_manifest_json_is_not_counted_as_a_data_file(raw_layer):
    """`manifest.json` is bookkeeping. Counting it would leave one file forever pending."""
    cursor = FakeCursor([("games", "c.json")])
    assert "games" not in loader.pending_by_endpoint(cursor, ["games"])


def test_an_endpoint_with_no_directory_is_not_pending(raw_layer):
    cursor = FakeCursor([])
    assert loader.pending_by_endpoint(cursor, ["never_fetched"]) == {}


def test_all_endpoints_lists_directories_only(raw_layer):
    (raw_layer / "data" / "raw" / "stray.json").write_text("{}", encoding="utf-8")
    assert loader.all_endpoints() == ["games", "lines"]


# --- one retry policy, every connection -----------------------------------------------

def test_the_pending_check_is_retried_like_everything_else(monkeypatch):
    """`sync` opened a bare connection twenty lines above a three-attempt loop.

    On 29 August a warehouse refusal landed on exactly that unprotected connect and killed
    the whole task in its pre-flight check, without the retry logic written for that failure
    ever running.
    """
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("BAD_REQUEST: Cannot create the resource")
        return "ok"

    monkeypatch.setattr(loader.time, "sleep", lambda _s: None)
    assert loader.with_retry(flaky, "pending check") == "ok"
    assert len(calls) == 3


def test_with_retry_reraises_once_the_attempts_are_spent(monkeypatch):
    monkeypatch.setattr(loader.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        loader.with_retry(lambda: (_ for _ in ()).throw(RuntimeError("still down")), "x")


def test_one_failing_endpoint_does_not_cost_the_others(monkeypatch):
    """A bad endpoint is recorded; the rest still load."""
    monkeypatch.setattr(loader.time, "sleep", lambda _s: None)
    monkeypatch.setattr(loader, "_load_one",
                        lambda e, s: (_ for _ in ()).throw(RuntimeError("no")) if e == "bad" else 5)
    total, failed = loader.load_endpoints(["good", "bad", "also_good"])
    assert total == 10 and failed == ["bad"]
