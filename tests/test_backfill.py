"""Tests for the historical backfill planner.

The plan is where scope rules live (PBP seasons, strategy expansion, per-game opt-in) and
where idempotency is decided, so it's worth testing without touching the network.
"""
import json

import pytest

from src import backfill
from src import endpoints as ep


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
                        lambda season: {"regular": ["1", "2"], "postseason": ["1"],
                                        "spring_regular": [], "spring_postseason": []})
    return backfill


def test_static_endpoints_are_fetched_once_regardless_of_seasons(planner):
    plan = planner.build_plan(["2024", "2025"], only=["venues"], bucket=None, per_game=False)
    assert plan == [("venues", {})]


def test_season_strategy_expands_per_season(planner):
    """The fix for the current-affiliation anachronism: one /teams call per season."""
    plan = planner.build_plan(["2024", "2025"], only=["teams"], bucket=None, per_game=False)
    assert plan == [("teams", {"year": "2024"}), ("teams", {"year": "2025"})]


def test_season_type_strategy_covers_every_season_type(planner):
    """Fetching only `regular` drops the bowl games; omitting the spring types dropped the
    entire 2020 FCS season, which was played in spring 2021 — 532 games found missing by the
    /records reconciliation test on 2026-08-18."""
    plan = planner.build_plan(["2024"], only=["games"], bucket=None, per_game=False)
    assert [p for _, p in plan] == [
        {"year": "2024", "seasonType": "regular"},
        {"year": "2024", "seasonType": "postseason"},
        {"year": "2024", "seasonType": "spring_regular"},
        {"year": "2024", "seasonType": "spring_postseason"},
    ]


def test_season_week_strategy_expands_over_weeks_and_season_types(planner):
    """Season types with no weeks contribute nothing — a season with no spring schedule
    costs no requests."""
    plan = planner.build_plan(["2024"], only=["plays"], bucket=None, per_game=False)
    assert [p for _, p in plan] == [
        {"year": "2024", "week": "1", "seasonType": "regular"},
        {"year": "2024", "week": "2", "seasonType": "regular"},
        {"year": "2024", "week": "1", "seasonType": "postseason"},
    ]


def test_pbp_endpoints_respect_the_data_scope(planner):
    """Play-by-play and drive detail are 2024-2026 only, per CLAUDE.md."""
    assert planner.build_plan(["2019"], only=["plays", "drives", "plays/stats"],
                              bucket=None, per_game=False) == []
    assert planner.build_plan(["2019"], only=["records"], bucket=None, per_game=False), \
        "season stats have no such restriction"


def test_manual_and_live_endpoints_never_produce_requests(planner):
    for path in ("player/search", "live/plays", "scoreboard"):
        assert planner.build_plan(["2024"], only=[path], bucket=None, per_game=False) == []


def test_per_game_requires_opt_in_and_landed_games(planner, tmp_path):
    """The expensive fan-out reads game ids from landed data, never from a guess."""
    assert planner.build_plan(["2024"], only=["metrics/wp"], bucket=None, per_game=False) == []

    # No /games landed yet -> nothing to fan out over, even when opted in.
    assert planner.build_plan(["2024"], only=["metrics/wp"], bucket=None, per_game=True) == []

    d = tmp_path / "data" / "raw" / "games"
    d.mkdir(parents=True)
    payload = [{"id": 401, "completed": True}, {"id": 402, "completed": False}]
    (d / "2026-01-01T00-00-00-000Z.json").write_text(json.dumps(
        {"status_code": 200, "params": {"year": "2024", "seasonType": "regular"}, "data": payload}))
    planner.manifest.add_entry("games", "2026-01-01T00-00-00-000Z.json",
                               {"year": "2024", "seasonType": "regular"}, 200)

    plan = planner.build_plan(["2024"], only=["metrics/wp"], bucket=None, per_game=True)
    # Only the completed game, and using this endpoint's own id parameter name.
    assert plan == [("metrics/wp", {"gameId": "401"})]


def test_bucket_filter_selects_one_cadence(planner):
    plan = planner.build_plan(["2024"], only=None, bucket=ep.BUCKET_PREGAME, per_game=False)
    assert plan, "bucket D should have members"
    assert {e for e, _ in plan} <= {x.path for x in ep.REGISTRY if x.bucket == ep.BUCKET_PREGAME}


def test_default_sweep_covers_the_whole_registry(planner):
    plan = planner.build_plan(["2024"], only=None, bucket=None, per_game=False)
    swept = {e for e, _ in plan}
    assert swept == {e.path for e in ep.SWEEPABLE}


def test_snapshot_endpoints_refetch_only_under_snapshot_flag(planner, monkeypatch):
    """Betting lines move: re-fetching identical params is the point, not a duplicate.

    Without this, the daily lines pull would be skipped from its second run onward and the
    movement series would never accumulate.
    """
    calls = []

    class Resp:
        status_code = 200

    monkeypatch.setattr(planner.ingest, "fetch",
                        lambda ep, params: calls.append((ep, params)) or Resp())
    monkeypatch.setattr(planner.time, "sleep", lambda s: None)
    planner.manifest.add_entry("lines", "a.json", {"year": "2025", "seasonType": "regular"}, 200)

    planner.run(["2025"], ["lines"], None, False, force=False, dry_run=False, snapshot=False)
    assert ("lines", {"year": "2025", "seasonType": "regular"}) not in calls, \
        "the already-fetched regular-season snapshot should be skipped"
    assert ("lines", {"year": "2025", "seasonType": "postseason"}) in calls

    calls.clear()
    planner.run(["2025"], ["lines"], None, False, force=False, dry_run=False, snapshot=True)
    assert ("lines", {"year": "2025", "seasonType": "regular"}) in calls, \
        "--snapshot must re-fetch even though the params are already present"


def test_non_snapshot_endpoints_ignore_the_snapshot_flag(planner, monkeypatch):
    """--snapshot must not turn the whole sweep into a re-fetch."""
    calls = []

    class Resp:
        status_code = 200

    monkeypatch.setattr(planner.ingest, "fetch",
                        lambda ep, params: calls.append((ep, params)) or Resp())
    monkeypatch.setattr(planner.time, "sleep", lambda s: None)
    planner.manifest.add_entry("teams", "a.json", {"year": "2025"}, 200)

    planner.run(["2025"], ["teams"], None, False, force=False, dry_run=False, snapshot=True)
    assert calls == []


def test_already_fetched_skips_only_successful_matching_params(planner):
    planner.manifest.add_entry("plays", "a.json", {"year": "2024", "week": "1"}, 200)
    planner.manifest.add_entry("plays", "b.json", {"year": "2024", "week": "2"}, 401)

    assert planner.already_fetched("plays", {"year": "2024", "week": "1"}) is True
    # A failed fetch must not count as done, or the gap would never be refilled.
    assert planner.already_fetched("plays", {"year": "2024", "week": "2"}) is False
    assert planner.already_fetched("plays", {"year": "2024", "week": "3"}) is False


def test_load_latest_raw_returns_newest_matching_payload(planner, tmp_path):
    """Planning reuses landed data instead of re-hitting the API — newest file wins."""
    d = tmp_path / "data" / "raw" / "calendar"
    d.mkdir(parents=True)
    for name, marker in (("2026-01-01T00-00-00-000Z.json", "old"),
                         ("2026-06-01T00-00-00-000Z.json", "new")):
        (d / name).write_text(json.dumps(
            {"status_code": 200, "params": {"year": "2024"}, "data": [marker]}))
        planner.manifest.add_entry("calendar", name, {"year": "2024"}, 200)

    assert planner.load_latest_raw("calendar", {"year": "2024"}) == ["new"]
    assert planner.load_latest_raw("calendar", {"year": "1999"}) is None


def test_full_history_expands_an_endpoint_across_its_own_availability(planner):
    """Depth comes from the registry's min_season, not from --seasons."""
    plan = planner.build_plan(["2024"], only=["draft/picks"], bucket=None, per_game=False,
                              full_history=True, current_season=2026)
    years = [p["year"] for _, p in plan]

    assert years[0] == "1967", "draft picks start at the common-draft era"
    assert years[-1] == "2026"
    assert len(years) == 2026 - 1967 + 1


def test_full_history_leaves_recent_scoped_endpoints_alone(planner):
    """PBP stays at 2024+ however the flag is passed — depth is per endpoint."""
    plan = planner.build_plan(["2024"], only=["plays"], bucket=None, per_game=False,
                              full_history=True, current_season=2026)
    assert plan == [], "plays is `recent`, so --full-history selects nothing for it"


def test_full_history_restricts_the_sweep_to_the_ratified_set(planner):
    """A stray flag must not pull 150 seasons of every endpoint."""
    plan = planner.build_plan(["2024"], only=None, bucket=None, per_game=False,
                              full_history=True, current_season=2026)
    swept = {e for e, _ in plan}

    assert swept == {e.path for e in ep.REGISTRY if e.history == ep.HISTORY_FULL}
    assert "plays" not in swept and "lines" not in swept
