"""Tests for the historical backfill planner.

The plan is where scope rules live (PBP seasons, season vs weekly endpoints) and where
idempotency is decided, so it's worth testing without touching the network.
"""
import pytest

from src import backfill


@pytest.fixture
def planner(tmp_path, monkeypatch):
    """Backfill wired to a throwaway raw dir, with the calendar stubbed.

    The manifest uses the same relative `data/raw` path the module reads from, so the
    manifest and the on-disk files agree the way they do in the real layout.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(backfill, "manifest",
                        backfill.RawManifest(base_dir=backfill.Path("data") / "raw"))
    monkeypatch.setattr(backfill, "season_weeks",
                        lambda season: {"regular": ["1", "2"], "postseason": ["1"]})
    return backfill


def test_plan_covers_static_season_and_weekly_endpoints(planner):
    plan = planner.build_plan(["2024"], only=None)
    endpoints = {ep for ep, _ in plan}

    assert {"conferences", "venues", "teams", "games", "drives", "plays", "games/teams"} == endpoints


def test_teams_is_season_scoped_without_season_type(planner):
    """The fix for the current-affiliation anachronism: one /teams call per season."""
    plan = planner.build_plan(["2024", "2025"], only=["teams"])

    assert plan == [("teams", {"year": "2024"}), ("teams", {"year": "2025"})]


def test_weekly_endpoints_expand_over_weeks_and_season_types(planner):
    plan = planner.build_plan(["2024"], only=["plays"])

    assert [p for _, p in plan] == [
        {"year": "2024", "week": "1", "seasonType": "regular"},
        {"year": "2024", "week": "2", "seasonType": "regular"},
        {"year": "2024", "week": "1", "seasonType": "postseason"},
    ]


def test_pbp_endpoints_respect_the_data_scope(planner):
    """Play-by-play and drives are 2024-2026 only, per CLAUDE.md."""
    plan = planner.build_plan(["2019"], only=["plays", "drives"])
    assert plan == []

    plan = planner.build_plan(["2019"], only=["games"])
    assert plan, "games has no such restriction"


def test_already_fetched_skips_only_successful_matching_params(planner):
    planner.manifest.add_entry("plays", "a.json", {"year": "2024", "week": "1"}, 200)
    planner.manifest.add_entry("plays", "b.json", {"year": "2024", "week": "2"}, 401)

    assert planner.already_fetched("plays", {"year": "2024", "week": "1"}) is True
    # A failed fetch must not count as done, or the gap would never be refilled.
    assert planner.already_fetched("plays", {"year": "2024", "week": "2"}) is False
    assert planner.already_fetched("plays", {"year": "2024", "week": "3"}) is False


def test_load_latest_raw_returns_newest_matching_payload(planner, tmp_path):
    """Planning reuses landed data instead of re-hitting the API — newest file wins."""
    import json

    d = tmp_path / "data" / "raw" / "calendar"
    d.mkdir(parents=True)
    for name, marker in (("2026-01-01T00-00-00-000Z.json", "old"),
                         ("2026-06-01T00-00-00-000Z.json", "new")):
        (d / name).write_text(json.dumps(
            {"status_code": 200, "params": {"year": "2024"}, "data": [marker]}))
        planner.manifest.add_entry("calendar", name, {"year": "2024"}, 200)

    assert planner.load_latest_raw("calendar", {"year": "2024"}) == ["new"]
    assert planner.load_latest_raw("calendar", {"year": "1999"}) is None
