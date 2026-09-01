"""Weather rides the lines cadence, and the reasons are worth pinning.

/games/weather sat in BUCKET_HISTORICAL, which no in-season refresh touches, so it was only
ever fetched by a backfill — 2026 had nothing at all until one was run by hand. For a game
already played that is fine; for the next game it is the difference between a forecast and a
record of one.
"""
from datetime import datetime, timezone

import pytest

from src import snapshot


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


def test_one_request_per_run_scoped_to_the_season_not_the_week(monkeypatch):
    """/games/weather is season-scoped and returns every game in the season type.

    Asking per week would return the same payload filtered, so a week loop would only make
    the job more expensive by making it more frequent — the opposite of why this endpoint is
    cheap enough to run four-hourly.
    """
    calls = []
    monkeypatch.setattr(snapshot, "current_week",
                        lambda season, now: {"year": season, "week": "3",
                                             "seasonType": "regular"})
    monkeypatch.setattr(snapshot.ingest, "fetch",
                        lambda ep, params: calls.append((ep, params)) or _Resp(
                            payload=[{"temperature": 70}, {"temperature": None}]))

    result = snapshot.snapshot_weather("2026", datetime(2026, 9, 15, tzinfo=timezone.utc))

    assert len(calls) == 1, "one request per run, not one per week"
    endpoint, params = calls[0]
    assert endpoint == "games/weather"
    assert params == {"year": "2026", "seasonType": "regular"}
    assert "week" not in params
    assert result["games"] == 2
    assert result["with_temperature"] == 1


def test_the_postseason_is_asked_for_by_name(monkeypatch):
    """A season type is not decoration: asking for `regular` in January returns nothing, and
    the bowl slate is exactly when a matchup page is being read."""
    seen = {}
    monkeypatch.setattr(snapshot, "current_week",
                        lambda season, now: {"year": season, "week": "1",
                                             "seasonType": "postseason"})
    monkeypatch.setattr(snapshot.ingest, "fetch",
                        lambda ep, params: seen.update(params) or _Resp())
    snapshot.snapshot_weather("2026", datetime(2026, 12, 28, tzinfo=timezone.utc))
    assert seen["seasonType"] == "postseason"


def test_no_active_week_is_a_skip_rather_than_a_failure(monkeypatch):
    """Out of season there is nothing to forecast. The gate already handles this, but a
    function that raised here would turn a correct idle run into an alert."""
    monkeypatch.setattr(snapshot, "current_week", lambda season, now: None)
    monkeypatch.setattr(snapshot.ingest, "fetch",
                        lambda *a, **k: pytest.fail("must not fetch with no active week"))
    result = snapshot.snapshot_weather("2030", datetime(2030, 5, 1, tzinfo=timezone.utc))
    assert result["status"] == "skipped"


def test_a_bad_response_raises_rather_than_recording_an_empty_season(monkeypatch):
    """A 500 that returned quietly would load zero rows over the top of a good season.

    The staging model keeps the latest file per params, so a silently-empty refresh is not a
    no-op — it is the newest answer, and it would win.
    """
    monkeypatch.setattr(snapshot, "current_week",
                        lambda season, now: {"year": season, "week": "3",
                                             "seasonType": "regular"})
    monkeypatch.setattr(snapshot.ingest, "fetch", lambda ep, params: _Resp(status_code=503))
    with pytest.raises(RuntimeError) as excinfo:
        snapshot.snapshot_weather("2026", datetime(2026, 9, 15, tzinfo=timezone.utc))
    assert "503" in str(excinfo.value)
