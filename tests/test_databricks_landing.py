"""The Databricks landing notebook's functions, with the API stubbed (cfdb-wtc-R-2570).

`notebooks/databricks/cfbd_landing_ingest.py` is a Databricks source-format notebook. Its Databricks
cells sit under `if __name__ == "__main__"`, so importing it here defines the functions and runs
nothing — no `dbutils`, no network. Every response below is hand-built, and each case is chosen so a
wrong implementation moves it.
"""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "databricks" / "cfbd_landing_ingest.py"
spec = importlib.util.spec_from_file_location("cfbd_landing_ingest", NOTEBOOK)
landing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(landing)

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
CALENDAR = [  # weeks 1 and 2 are over at NOW; week 3 is not; a postseason entry is ignored
    {"season": 2026, "week": 1, "seasonType": "regular", "endDate": "2026-09-08T06:59:00.000Z"},
    {"season": 2026, "week": 2, "seasonType": "regular", "endDate": "2026-09-15T06:59:00.000Z"},
    {"season": 2026, "week": 3, "seasonType": "regular", "endDate": "2026-10-05T06:59:00.000Z"},
    {"season": 2026, "week": 1, "seasonType": "postseason", "endDate": "2026-01-01T00:00:00.000Z"},
]


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.content = body if isinstance(body, bytes) else json.dumps(body).encode()


def stub(overrides=None):
    """A fake `requests.get`: calendar, then distinct elements per (endpoint, week). Records calls."""
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        path = url.replace(landing.BASE_URL, "")
        calls.append((path, dict(params or {})))
        key = (path, (params or {}).get("week"))
        if overrides and key in overrides:
            return overrides[key]
        if path == "/calendar":
            return Response(200, CALENDAR)
        week = params["week"]
        return Response(200, [{"endpoint": path, "week": week, "i": i} for i in range(week + 1)])
    return get, calls


def run(tmp_path, overrides=None, **kw):
    get, calls = stub(overrides)
    rows = landing.land(2026, "test-key", now=NOW, http_get=get, pace=0, sleep=lambda s: None, **kw)
    return rows, calls


def _elements(path):
    return json.loads(Path(path).read_bytes())


def test_completed_weeks_are_regular_season_weeks_whose_end_date_has_passed():
    assert landing.completed_weeks(CALENDAR, NOW) == [1, 2]


def test_both_batches_hold_the_same_elements_in_week_order(tmp_path):
    rows, _ = run(tmp_path, one_shot_root=str(tmp_path / "one"), weekly_root=str(tmp_path / "wk"))
    for name in landing.GAME_ENDPOINTS:
        one_shot = _elements(tmp_path / "one" / name / f"{name}_2026.json")
        weekly = [e for wk in (1, 2) for e in _elements(tmp_path / "wk" / name / f"{name}_2026_wk{wk:02d}.json")]
        assert one_shot == weekly and len(one_shot) == 2 + 3     # week 1 has 2 elements, week 2 has 3
    assert not (tmp_path / "wk" / "games" / "games_2026_wk03.json").exists(), "an unfinished week was landed"


def test_each_endpoint_week_is_fetched_once_even_when_both_batches_are_written(tmp_path):
    _, calls = run(tmp_path, one_shot_root=str(tmp_path / "one"), weekly_root=str(tmp_path / "wk"))
    assert len(calls) == 1 + 3 * 2 and len(set(map(str, calls))) == len(calls)


def test_a_weekly_file_is_the_response_body_byte_for_byte(tmp_path):
    body = b'[{"id": 1,   "spacing": "kept"}]'
    run(tmp_path, overrides={("/games", 1): Response(200, body)}, weekly_root=str(tmp_path / "wk"))
    assert (tmp_path / "wk" / "games" / "games_2026_wk01.json").read_bytes() == body


def test_one_mode_alone_writes_only_its_volume(tmp_path):
    run(tmp_path, weekly_root=str(tmp_path / "wk"))
    assert (tmp_path / "wk" / "games").is_dir() and not (tmp_path / "one").exists()


def test_a_non_200_raises(tmp_path):
    with pytest.raises(landing.LandingError, match="HTTP 500"):
        run(tmp_path, overrides={("/games/teams", 2): Response(500, {"error": "x"})},
            one_shot_root=str(tmp_path / "one"))


def test_an_empty_completed_week_raises(tmp_path):
    with pytest.raises(landing.LandingError, match="came back empty"):
        run(tmp_path, overrides={("/games/players", 1): Response(200, [])}, weekly_root=str(tmp_path / "wk"))


def test_a_body_that_is_not_an_array_raises(tmp_path):
    with pytest.raises(landing.LandingError, match="not a JSON array"):
        run(tmp_path, overrides={("/games", 2): Response(200, {"message": "rate limited"})},
            weekly_root=str(tmp_path / "wk"))


def test_asking_for_an_unfinished_week_raises(tmp_path):
    with pytest.raises(landing.LandingError, match="not completed"):
        run(tmp_path, weekly_root=str(tmp_path / "wk"), weeks=[3])


def test_a_429_backs_off_and_retries(tmp_path):
    attempts = []

    def get(url, params=None, headers=None, timeout=None):
        attempts.append(url)
        return Response(429, b"") if len(attempts) == 1 else Response(200, CALENDAR)
    raw, body = landing.fetch("/calendar", {"year": 2026}, "k", http_get=get, pace=0, sleep=lambda s: None)
    assert len(attempts) == 2 and body == CALENDAR


def test_the_key_and_no_host_or_user_path_are_written_into_the_notebook():
    text = NOTEBOOK.read_text()
    assert "Bearer {api_key}" in text and "dbutils.secrets.get" in text
    for forbidden in ("/Users/", "CFBD_API_KEY=", "143.", "root@"):
        assert forbidden not in text, forbidden


def test_a_week_list_is_refused_for_the_one_shot_batch(tmp_path):
    """The one-shot file is every completed week; a week list would overwrite it with fewer."""
    with pytest.raises(ValueError, match="every completed week"):
        run(tmp_path, one_shot_root=str(tmp_path / "one"), weeks=[2])


def test_a_week_list_rewrites_only_that_weeks_weekly_files(tmp_path):
    run(tmp_path, weekly_root=str(tmp_path / "wk"), weeks=[2])
    assert sorted(p.name for p in (tmp_path / "wk" / "games").iterdir()) == ["games_2026_wk02.json"]
