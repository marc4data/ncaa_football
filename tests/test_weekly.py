"""Tests for the in-season weekly refreshes."""
from datetime import datetime, timezone

import pytest

from src import weekly
from src.endpoints import BUCKET_IMMUTABLE_WK, BUCKET_PREGAME, BUCKET_REVISIONIST

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
    weeks = [{"year": "2026", "week": "2", "seasonType": "regular"},
             {"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_IMMUTABLE_WK, "2026", weeks)

    assert requests, "bucket C2 should have members"
    assert all("week" in params for _, params in requests), \
        "C2 endpoints must be week-scoped, not season-scoped"
    assert {params["week"] for _, params in requests} == {"2", "3"}


def test_revisionist_bucket_is_season_scoped():
    """C1 revises retroactively, so it is re-pulled whole rather than by week."""
    weeks = [{"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_REVISIONIST, "2026", weeks)

    assert requests
    assert all("week" not in params for _, params in requests)


def test_pregame_bucket_targets_the_upcoming_week_only():
    weeks = [{"year": "2026", "week": "3", "seasonType": "regular"}]
    requests = weekly._requests_for_bucket(BUCKET_PREGAME, "2026", weeks)

    assert requests
    assert all(params["week"] == "3" for _, params in requests)


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


def test_the_expensive_per_game_endpoints_stay_out_of_the_weekly_refresh(monkeypatch):
    """game/box/advanced and metrics/wp fan out for volume, not correctness, and remain
    backfill-only. Adding them here would triple the weekly call count as a side effect."""
    monkeypatch.setattr("src.backfill.completed_game_ids",
                        lambda season, weeks=None: ["111"])
    weeks = [{"year": "2026", "week": "2", "seasonType": "regular"}]
    paths = {path for path, _ in
             weekly._requests_for_bucket(BUCKET_IMMUTABLE_WK, "2026", weeks)}
    assert "game/box/advanced" not in paths
    assert "metrics/wp" not in paths
