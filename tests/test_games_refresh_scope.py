"""R-656 / R-658 — the weekly refresh must ask for the WHOLE SEASON of kickoffs.

🚨 THE DEFECT THIS GUARDS IS A TEST-SHAPED ONE: every DAG reported success while 63% of the
season's kickoff times went stale. Measured 2026-09-11: 1,293 of the 2,053 games in the 2026
regular season carried a kickoff last fetched on 2026-08-15, because `/games` sat in
BUCKET_HISTORICAL — "immutable once the season completes" — which no weekly refresh expands.

⚠️ AND THE OBVIOUS FIX WOULD HAVE SHIPPED GREEN. Moving `/games` to BUCKET_PREGAME lands it in
weekly.py's week-scoping branch, and `pregame_refresh` asks for the current week ALONE — one
request, narrower than the two `scores_refresh` already manages. So these tests assert the
REQUEST LIST, never the bucket string: a test that checks which bucket an endpoint is in would
pass for both the fix and the wrong fix.

Marc, 2026-09-11, authorising the quota cost: *"you take it."*
"""
from datetime import datetime, timezone

import pytest

from src import weekly
from src.endpoints import BUCKET_PREGAME, REGISTRY

CALENDAR = [
    {"season": 2026, "week": 2, "seasonType": "regular",
     "startDate": "2026-09-11T00:00:00.000Z", "endDate": "2026-09-14T00:00:00.000Z"},
    {"season": 2026, "week": 3, "seasonType": "regular",
     "startDate": "2026-09-18T00:00:00.000Z", "endDate": "2026-09-21T00:00:00.000Z"},
]

# The endpoints whose freshness is a whole-season question rather than a this-week question.
# ⚠️ Written out rather than derived from the flag it checks — a guard filtered from the thing
# it guards cannot fail, which A089 proved by shipping one that could not.
WHOLE_SEASON = {"games", "games/media"}


@pytest.fixture(autouse=True)
def stub_calendar(monkeypatch):
    monkeypatch.setattr(weekly, "_calendar", lambda season: CALENDAR)
    monkeypatch.setattr("src.snapshot._calendar", lambda season: CALENDAR)


def _pregame_requests(season_type="regular", week="3"):
    weeks = [{"year": "2026", "week": week, "seasonType": season_type}]
    return weekly._requests_for_bucket(BUCKET_PREGAME, "2026", weeks)


def test_the_weekly_run_asks_for_the_whole_season_of_kickoffs():
    """🚨 THE ROUND. A whole-season `/games` request, with no `week` in it."""
    requests = _pregame_requests()
    assert ("games", {"year": "2026", "seasonType": "regular"}) in requests, (
        "the weekly pregame run does not ask for the whole season's games. A kickoff time "
        "that moves for a game three weeks out will never be re-fetched, which is R-656: "
        "1,293 of 2,053 games held a kickoff from 2026-08-15. Requests were: "
        f"{[(p, q) for p, q in requests if p == 'games']}")


def test_the_broadcast_assignments_are_asked_for_the_whole_season_too():
    """R-658 — the precedent this copied had the same hole.

    `games/media` was moved out of BUCKET_HISTORICAL because broadcast assignments are
    "announced roughly twelve days ahead and change up to game week". It landed in a
    week-scoped bucket, so a game twelve days out was never in the request. Measured on
    raw_games_media for 2026: weeks 1 and 2 only, plus one whole-season pull on 2026-08-21.
    """
    assert ("games/media", {"year": "2026", "seasonType": "regular"}) in _pregame_requests()


def test_no_whole_season_endpoint_is_asked_one_week_at_a_time():
    """The general property, so a third endpoint cannot regress quietly."""
    for path, params in _pregame_requests():
        if path in WHOLE_SEASON:
            assert "week" not in params, (
                f"{path} is week-scoped on the weekly run. That is the R-656 defect: it "
                f"looks like a refresh and covers one week of a fifteen-week season.")


def test_the_snapshot_endpoints_are_left_alone():
    """🚨 THE OTHER HALF OF THE DECISION, AND IT IS A REAL CONSTRAINT.

    `lines` and `metrics/wp/pregame` are also declared SEASON_TYPE, so a fix that simply
    respected the declared strategy would have widened two SNAPSHOT endpoints to a whole
    season on every run — a quota change nobody asked for, shipped as a side effect. The
    opt-out is per endpoint precisely so that does not happen.
    """
    week_scoped = {path for path, params in _pregame_requests() if "week" in params}
    assert week_scoped == {"lines", "metrics/wp/pregame"}, (
        f"the set of week-scoped pregame endpoints changed: {week_scoped}")


def test_the_postseason_is_not_invisible_from_december():
    """Both season types, which is what the SEASON_TYPE branch already existed to do.

    Its own comment: "otherwise every bowl and playoff game would be invisible to the weekly
    refresh from December onward, while the DAG still reported success."
    """
    requests = _pregame_requests(season_type="postseason", week="1")
    games = [params for path, params in requests if path == "games"]
    assert {p["seasonType"] for p in games} == {"regular", "postseason"}, (
        f"in December the weekly run asks for {games} — a bowl slate whose kickoffs move is "
        f"exactly when this matters.")
    assert all("week" not in p for p in games)


def test_the_registry_still_declares_games_fetchable_in_season():
    """A bucket no weekly refresh expands is how this defect existed for a season.

    ⚠️ Asserts the CONSEQUENCE as well: `pregame_refresh` is the run that must carry it, so
    the endpoint has to be in a bucket that run expands.
    """
    games = next(e for e in REGISTRY if e.path == "games")
    assert games.bucket == BUCKET_PREGAME
    assert games.extra.get("weekly_whole_season") is True
    # And the end-to-end shape, through the real refresh entry point rather than the helper.
    weeks = weekly.week_window("2026", datetime(2026, 9, 15, tzinfo=timezone.utc),
                               include_prior=False)
    assert weeks, "no week in play — the fixture calendar is wrong"
    built = (weekly._requests_for_bucket(BUCKET_PREGAME, "2026", weeks))
    assert any(path == "games" and "week" not in params for path, params in built)
