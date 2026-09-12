"""Tests for the in-season weekly refreshes."""
from datetime import datetime, timezone

import pytest

from src import weekly
from src.endpoints import (BUCKET_IMMUTABLE_WK, BUCKET_PREGAME, BUCKET_REVISIONIST,
                           PER_GAME, REGISTRY)

CALENDAR = [
    {"season": 2026, "week": 1, "seasonType": "regular",
     "startDate": "2026-08-27T00:00:00.000Z", "endDate": "2026-09-07T00:00:00.000Z"},
    {"season": 2026, "week": 2, "seasonType": "regular",
     "startDate": "2026-09-11T00:00:00.000Z", "endDate": "2026-09-14T00:00:00.000Z"},
    {"season": 2026, "week": 3, "seasonType": "regular",
     "startDate": "2026-09-18T00:00:00.000Z", "endDate": "2026-09-21T00:00:00.000Z"},
]


@pytest.fixture(autouse=True)
def stub_calendar(monkeypatch):
    monkeypatch.setattr(weekly, "_calendar", lambda season: CALENDAR)
    monkeypatch.setattr("src.snapshot._calendar", lambda season: CALENDAR)


@pytest.fixture(autouse=True)
def stub_completed_games(monkeypatch):
    """🚨 R-662: THREE TESTS IN THIS FILE READ THE LIVE WAREHOUSE, AND NOBODY KNEW.

    `_requests_for_bucket` fans PER_GAME endpoints out over `completed_game_ids`, which reads
    already-landed /games responses out of `raw.raw_games`. So the request list this file
    asserts on depended on what was in a database — and on whether one was reachable at all.

    ⚠️ A099 FOUND THAT THE HARD WAY. `test_week_scoped_buckets_expand_over_the_window` had been
    passing only because no week-2 game had finished yet; the moment A099 landed a fresh
    whole-season fetch, real game ids appeared, `plays/stats` started contributing
    `{gameId: ...}` requests with no `week` in them, and the assertion broke on DATA rather
    than on code. It would have broken by itself on the next Saturday.

    ✅ Measured by A101 with `completed_game_ids` made to raise: THREE tests reach the
    warehouse — that one, `test_results_refresh_reports_touched_endpoints` and
    `test_a_partial_refresh_raises_rather_than_reporting_success`. All three assert invariants
    that do not depend on HOW MANY games come back (a week is scoped or it is not; fetched
    equals requested or it does not), so a fixed pair of ids makes them deterministic without
    weakening a single assertion.

    ⚠️ A unit test whose outcome depends on whether a database is reachable is a test that
    reports on the world rather than on the code.
    """
    monkeypatch.setattr("src.backfill.completed_game_ids",
                        lambda season, weeks=None: ["401000001", "401000002"])


def test_week_window_includes_the_prior_week():
    """Stat corrections land late, so the week before the one in play is refreshed too."""
    window = weekly.week_window("2026", datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert [w["week"] for w in window] == ["2", "3"]


def test_week_window_has_no_prior_before_the_first_week():
    window = weekly.week_window("2026", datetime(2026, 8, 28, tzinfo=timezone.utc))
    assert [w["week"] for w in window] == ["1"]


def test_week_window_can_omit_the_prior_week():
    window = weekly.week_window("2026", datetime(2026, 9, 20, tzinfo=timezone.utc),
                                include_prior=False)
    assert [w["week"] for w in window] == ["3"]


def test_week_window_is_empty_after_the_season():
    assert weekly.week_window("2026", datetime(2027, 6, 1, tzinfo=timezone.utc)) == []


def test_week_scoped_buckets_expand_over_the_window():
    """The BULK C2 endpoints are week-scoped.

    ⚠️ PER_GAME ENDPOINTS ARE EXCLUDED, AND THEY ALWAYS SHOULD HAVE BEEN. `plays/stats` opts
    into the weekly sweep via `weekly_per_game` and fans out as `{gameId: ...}` — game-scoped,
    which is a different axis from week-versus-season and carries no `week` key at all.

    🚨 THIS TEST HAS A HIDDEN DEPENDENCY ON LIVE WAREHOUSE DATA, found by A099 rather than
    designed. `_requests_for_bucket` calls `completed_game_ids`, which reads already-landed
    /games responses out of `raw.raw_games`. While no week-2 game had finished, that returned
    nothing, `plays/stats` contributed no requests, and the blanket `all("week" in params)`
    held by accident. A099 landed a fresh whole-season /games fetch, week-2 completions
    appeared, and the assertion broke on data rather than on code. It would have broken by
    itself on the next Saturday.
    """
    weeks = [{"year": "2026", "week": "2", "seasonType": "regular"},
             {"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_IMMUTABLE_WK, "2026", weeks)

    assert requests, "bucket C2 should have members"
    # ⚠️ EXCLUDED BY STRATEGY, NOT BY NAME. This read `path != "plays/stats"` until R-697 added
    # a second weekly per-game endpoint and the hardcoded name stopped covering the case the
    # docstring above already described. Deriving it from the registry means the next opt-in
    # does not silently break an assertion about a different axis.
    per_game_paths = {e.path for e in REGISTRY if e.strategy == PER_GAME}
    bulk = [(path, params) for path, params in requests if path not in per_game_paths]
    assert all("week" in params for _, params in bulk), \
        "C2 endpoints must be week-scoped, not season-scoped"
    assert {params["week"] for _, params in bulk} == {"2", "3"}


def test_revisionist_bucket_is_season_scoped():
    """C1 revises retroactively, so it is re-pulled whole rather than by week."""
    weeks = [{"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_REVISIONIST, "2026", weeks)

    assert requests
    assert all("week" not in params for _, params in requests)


def test_pregame_snapshot_endpoints_target_the_upcoming_week_only():
    """The SNAPSHOT endpoints stay week-scoped, and that is a quota guard.

    ⚠️ THIS TEST USED TO ASSERT IT OF THE WHOLE BUCKET, and that assumption is what R-656
    and R-658 were. Week-scoping is right for a line that moves through the week in play; it
    is wrong for a kickoff time three weeks out. The split is now per endpoint
    (`weekly_whole_season`), so the guard splits with it rather than being deleted.

    🚨 Widening `lines` or `metrics/wp/pregame` to a whole season on every run would be a
    quota change nobody asked for. If this goes red because one of them lost its week, that
    is the finding, not an inconvenience.
    """
    weeks = [{"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_PREGAME, "2026", weeks)

    week_scoped = {path for path, params in requests if "week" in params}
    assert week_scoped == {"lines", "metrics/wp/pregame"}, (
        f"the week-scoped pregame endpoints changed: {week_scoped}")
    assert all(params["week"] == "3"
               for _, params in requests if "week" in params)


def test_results_refresh_reports_touched_endpoints(monkeypatch):
    class Resp:
        status_code = 200

    monkeypatch.setattr(weekly.ingest, "fetch", lambda ep, params: Resp())
    summary = weekly.results_refresh("2026", datetime(2026, 9, 20, tzinfo=timezone.utc))

    assert summary["status"] == "ok"
    assert summary["failed"] == 0
    assert summary["fetched"] == summary["requests"]
    # Directory keys, so the load step can reload exactly what changed.
    assert "games_teams" in summary["endpoints"]


def test_a_partial_refresh_raises_rather_than_reporting_success(monkeypatch):
    class Resp:
        def __init__(self, code):
            self.status_code = code

    calls = {"n": 0}

    def flaky(endpoint, params):
        calls["n"] += 1
        return Resp(500 if calls["n"] % 3 == 0 else 200)

    monkeypatch.setattr(weekly.ingest, "fetch", flaky)

    with pytest.raises(RuntimeError, match="requests failed"):
        weekly.results_refresh("2026", datetime(2026, 9, 20, tzinfo=timezone.utc))


def test_refresh_outside_the_season_is_a_clean_skip(monkeypatch):
    monkeypatch.setattr(weekly.ingest, "fetch",
                        lambda ep, params: pytest.fail("should not fetch out of season"))
    summary = weekly.results_refresh("2026", datetime(2027, 6, 1, tzinfo=timezone.utc))

    assert summary["status"] == "skipped"
    assert summary["requests"] == 0


def test_season_scoped_endpoints_cover_the_season_type_in_play():
    """December regression: hardcoding `regular` made every bowl game invisible.

    The weekly refresh runs during the postseason too, and the season-scoped endpoints are
    asked per seasonType — so a postseason week must produce postseason requests.
    """
    postseason_week = [{"year": "2026", "week": "1", "seasonType": "postseason"}]
    requests = weekly._requests_for_bucket(BUCKET_REVISIONIST, "2026", postseason_week)
    season_types = {p.get("seasonType") for _, p in requests if "seasonType" in p}

    assert "postseason" in season_types, "bowl-season data would be silently missed"
    # `regular` stays in the set: cumulative season stats still revise during the postseason.
    assert "regular" in season_types


def test_regular_season_weeks_do_not_request_postseason():
    """No wasted calls during the regular season — the week in play decides."""
    regular_week = [{"year": "2026", "week": "5", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_REVISIONIST, "2026", regular_week)
    season_types = {p.get("seasonType") for _, p in requests if "seasonType" in p}

    assert season_types == {"regular"}


def test_the_weekly_refresh_fans_plays_stats_out_per_game(monkeypatch):
    """/plays/stats is PER_GAME and therefore `include=False`, which the bucket loop skips.

    Without an explicit branch it would silently vanish from the weekly refresh the moment
    its strategy changed — trading a truncated feed for no feed at all, and the DAG would
    still report success. This pins that the branch exists and is week-scoped.
    """
    monkeypatch.setattr("src.backfill.completed_game_ids",
                        lambda season, weeks=None: ["111", "222"] if weeks else ["999"])
    weeks = [{"year": "2026", "week": "2", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_IMMUTABLE_WK, "2026", weeks)

    plays_stats = [params for path, params in requests if path == "plays/stats"]
    assert plays_stats == [{"gameId": "111"}, {"gameId": "222"}], (
        "the weekly refresh must fan /plays/stats out per game, scoped to the weeks in play")


def test_metrics_wp_stays_out_of_the_weekly_refresh_and_box_advanced_is_in(monkeypatch):
    """The two PER_GAME volume endpoints now sit on opposite sides of the weekly marker.

    game/box/advanced joined the weekly refresh in R-697 — it carries the only per-game
    participation share in the warehouse, and the backfill that fed it never asked about the
    current season.

    🚨 metrics/wp DID NOT, and that is the half worth guarding. It has no reader and no request
    behind it, and taking it along would be exactly the "side effect of fixing something else"
    the note in weekly.py was written to prevent. Measured on a two-week window, opting one in
    took results_refresh from 139 requests to 239; opting both in would have been worse for
    nothing.
    """
    monkeypatch.setattr("src.backfill.completed_game_ids",
                        lambda season, weeks=None: ["111"])
    weeks = [{"year": "2026", "week": "2", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_IMMUTABLE_WK, "2026", weeks)
    paths = {path for path, _ in requests}

    assert "metrics/wp" not in paths
    assert ("game/box/advanced", {"id": "111"}) in requests, (
        "box/advanced must fan out per game, scoped to the weeks in play")
