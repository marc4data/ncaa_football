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
