"""Point-in-time snapshots of endpoints whose answers move.

Betting lines change until kickoff, and the movement is itself the signal — action
shifting toward a team, a late injury. CFBD serves only the current state plus an opening
value, so the path between them exists only if we sample it.

This module is the reusable unit an Airflow task calls. It deliberately contains no
transforms and no scheduling: Airflow decides *when*, this decides *what*, and dbt decides
what any of it means.

Why the current week, not the season
------------------------------------
A season-scoped /lines call returns ~1,550 games and 1.65 MB; a week-scoped call returns
~106 games and 0.11 MB. Fifteen times smaller, and the difference is entirely games that
have already been played, whose lines can no longer move. At hourly sampling that is the
difference between ~4.8 GB and ~320 MB across a season.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ingest
from .backfill import load_latest_raw

SEASON_TYPES = ["regular", "postseason"]


def _calendar(season: str) -> List[Dict[str, Any]]:
    """The season's calendar, from raw if landed, otherwise fetched."""
    payload = load_latest_raw("calendar", {"year": season})
    if payload is None:
        resp = ingest.fetch("calendar", {"year": season})
        if resp.status_code != 200:
            raise RuntimeError(f"calendar fetch for {season} returned {resp.status_code}")
        payload = resp.json()
    return payload


def current_week(season: str, now: Optional[datetime] = None) -> Optional[Dict[str, str]]:
    """The week whose games haven't all finished yet — the only week whose lines can move.

    Returns the *upcoming* week during the preseason, so snapshots can begin before the
    opener: line movement into week 1 is exactly what the first snapshots should capture.
    Returns None once the season is over.
    """
    now = now or datetime.now(timezone.utc)
    upcoming = [
        entry for entry in _calendar(season)
        if datetime.fromisoformat(entry["endDate"].replace("Z", "+00:00")) >= now
    ]
    if not upcoming:
        return None

    nearest = min(upcoming, key=lambda e: e["startDate"])
    return {
        "year": str(nearest["season"]),
        "week": str(nearest["week"]),
        "seasonType": nearest["seasonType"],
    }


def snapshot_weather(season: Optional[str] = None,
                     now: Optional[datetime] = None) -> Dict[str, Any]:
    """Re-fetch /games/weather for the season type currently in play.

    WHY THIS RIDES THE LINES CADENCE. Weather sat in BUCKET_HISTORICAL, which no in-season
    refresh touches, so it was only ever fetched by a backfill — 2026 had nothing at all
    until one was run by hand. For a game already played that is fine; for the next game it
    is the difference between a forecast and a record of one, and a forecast nobody refreshes
    is not a forecast.

    The lines cadence is the right home for it. Both are pre-game information that moves as
    kickoff approaches, both are cheap, and both are pointless out of season — so weather
    inherits the same short-circuit gate rather than needing a season window of its own.

    ONE REQUEST PER RUN, not one per week: /games/weather is season-scoped and returns every
    game in the season type, so a week filter would only make it more expensive by making it
    more frequent. At a four-hourly cadence that is roughly 180 calls a month against a
    75,000 quota currently sitting near 2,300.

    Returns a summary rather than raising on an empty result: a season type with no weather
    yet published is a normal early-season state, not a failure.
    """
    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)

    target = current_week(season, now)
    if target is None:
        return {
            "status": "skipped",
            "reason": f"no active or upcoming week in {season}",
            "games": 0,
        }

    params = {"year": season, "seasonType": target["seasonType"]}
    resp = ingest.fetch("games/weather", params)
    if resp.status_code != 200:
        raise RuntimeError(f"games/weather for {params} returned {resp.status_code}")

    games = resp.json()
    return {
        "status": "ok",
        "params": params,
        "games": len(games),
        "with_temperature": sum(1 for g in games if g.get("temperature") is not None),
    }


def snapshot_lines(season: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Land one /lines snapshot for the week currently in play.

    Returns a small summary dict — Airflow surfaces it in the task log and XCom, which is
    enough to see at a glance whether a run captured anything.
    """
    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)

    target = current_week(season, now)
    if target is None:
        return {"status": "skipped", "reason": f"no active or upcoming week in {season}", "games": 0}

    resp = ingest.fetch("lines", target)
    if resp.status_code != 200:
        raise RuntimeError(f"lines snapshot for {target} returned {resp.status_code}")

    games = resp.json()
    with_lines = [g for g in games if g.get("lines")]
    return {
        "status": "ok",
        "params": target,
        "games": len(games),
        "games_with_lines": len(with_lines),
        "providers": sorted({line["provider"] for g in with_lines for line in g["lines"]}),
    }
