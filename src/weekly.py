"""In-season weekly refreshes.

Two cadences, both driven by the cadence buckets in `src/endpoints.py` rather than by a
second list that could drift from it:

  Sunday  — results refresh. Bucket C2 (immutable once a week completes) for the week just
            played *and* the one before it, because stat corrections land late; plus bucket
            C1 (ratings, cumulative stats), which revises retroactively and is re-pulled
            whole.
  Tuesday — pre-game refresh. Bucket D (lines, pre-game win probability) for the upcoming
            week, plus C1 again, since polls and ratings publish early in the week.

Both force a re-fetch. The params match earlier requests by design — that is what makes
them refreshes — so the manifest's skip-if-present logic is deliberately bypassed here,
and staging's latest-file-per-params rule collapses the overlap.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ingest
from .endpoints import (
    BUCKET_IMMUTABLE_WK, BUCKET_PREGAME, BUCKET_REVISIONIST, REGISTRY, SEASON, SEASON_TYPE,
    SEASON_WEEK,
)
from .snapshot import _calendar, current_week


def week_window(season: str, now: Optional[datetime] = None,
                include_prior: bool = True) -> List[Dict[str, str]]:
    """The week in play, plus the one before it — the weeks whose data can still change."""
    now = now or datetime.now(timezone.utc)
    target = current_week(season, now)
    if target is None:
        return []

    window = [target]
    if include_prior:
        calendar = sorted(_calendar(season), key=lambda e: e["startDate"])
        for i, entry in enumerate(calendar):
            same = (str(entry["week"]) == target["week"]
                    and entry["seasonType"] == target["seasonType"])
            if same and i > 0:
                prior = calendar[i - 1]
                window.insert(0, {"year": str(prior["season"]), "week": str(prior["week"]),
                                  "seasonType": prior["seasonType"]})
            if same:
                break
    return window


def _requests_for_bucket(bucket: str, season: str,
                         weeks: List[Dict[str, str]]) -> List[tuple]:
    """Expand a cadence bucket into concrete requests for this refresh."""
    out: List[tuple] = []
    for endpoint in REGISTRY:
        if endpoint.bucket != bucket or not endpoint.include:
            continue

        if bucket in (BUCKET_IMMUTABLE_WK, BUCKET_PREGAME):
            # Week-scoped: every endpoint in these buckets accepts an optional `week`,
            # so scope them all to the affected weeks rather than the whole season.
            for week in weeks:
                out.append((endpoint.path, dict(week)))
        elif endpoint.strategy == SEASON_TYPE:
            # Both season types, not just `regular`. The weeks in play carry their own
            # seasonType, but these endpoints are season-scoped and so must be asked for
            # each — otherwise every bowl and playoff game would be invisible to the
            # weekly refresh from December onward, while the DAG still reported success.
            for season_type in {w["seasonType"] for w in weeks} | {"regular"}:
                out.append((endpoint.path, {"year": season, "seasonType": season_type}))
        elif endpoint.strategy == SEASON:
            out.append((endpoint.path, {"year": season}))
        elif endpoint.strategy == SEASON_WEEK:
            for week in weeks:
                out.append((endpoint.path, dict(week)))
    return out


def _run(requests: List[tuple]) -> Dict[str, Any]:
    """Fetch each request, collecting failures rather than stopping at the first."""
    fetched, failures, touched = 0, [], set()
    for endpoint, params in requests:
        resp = ingest.fetch(endpoint, params)
        touched.add(endpoint.replace("/", "_"))
        if resp.status_code == 200:
            fetched += 1
        else:
            failures.append(f"{endpoint} {params} -> {resp.status_code}")

    summary = {"requests": len(requests), "fetched": fetched,
               "failed": len(failures), "endpoints": sorted(touched)}
    if failures:
        summary["failures"] = failures
        # Loud: a partial refresh must not read as a success.
        raise RuntimeError(f"{len(failures)} of {len(requests)} requests failed: {failures[:5]}")
    return summary


def results_refresh(season: Optional[str] = None,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Sunday: what just happened, plus everything that revises because of it."""
    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)
    weeks = week_window(season, now, include_prior=True)
    if not weeks:
        return {"status": "skipped", "reason": f"no active week in {season}", "requests": 0}

    requests = (_requests_for_bucket(BUCKET_IMMUTABLE_WK, season, weeks)
                + _requests_for_bucket(BUCKET_REVISIONIST, season, weeks))
    return {"status": "ok", "weeks": weeks, **_run(requests)}


def scores_refresh(season: Optional[str] = None,
                   now: Optional[datetime] = None) -> Dict[str, Any]:
    """The game spine only: who played, what the score was, is it final.

    THIS IS THE CHEAP ONE, and being cheap is what makes it frequent. A full
    results_refresh is 31 requests — plays, drives, box scores, PPA, ratings — and running
    that every few hours through a season would cost roughly half the monthly quota to
    re-fetch data that does not change between Saturday night and Sunday morning.

    The Scores page needs one thing to stop lying: /games. That is TWO requests for the
    weeks in play, so this can run on a fine cadence and the heavy refresh can stay weekly.

    Why it matters for the opening weekend specifically: cfbd_midweek_results fires at 12:00
    UTC on Thursday, ten hours BEFORE Thursday's 22:00 kickoffs, and the next results run is
    Sunday. Without this, the twenty games of 27 August sit on the site marked "scheduled"
    until Sunday the 30th — and Scores is the most-visited surface on any sports site during
    a game week.

    Safe to run mid-slate, which is the property that lets it be frequent. CFBD reports
    `completed: false` for a game in progress, so a live game stays out of the completed set
    rather than being recorded as final at whatever the score was when we asked.
    """
    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)
    weeks = week_window(season, now, include_prior=True)
    if not weeks:
        return {"status": "skipped", "reason": f"no active week in {season}", "requests": 0}

    requests = [("games", dict(week)) for week in weeks]
    return {"status": "ok", "weeks": weeks, **_run(requests)}


def pregame_refresh(season: Optional[str] = None,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Tuesday: what's expected to happen next, and the ratings that inform it."""
    now = now or datetime.now(timezone.utc)
    season = season or str(now.year)
    weeks = week_window(season, now, include_prior=False)
    if not weeks:
        return {"status": "skipped", "reason": f"no upcoming week in {season}", "requests": 0}

    requests = (_requests_for_bucket(BUCKET_PREGAME, season, weeks)
                + _requests_for_bucket(BUCKET_REVISIONIST, season, weeks))
    return {"status": "ok", "weeks": weeks, **_run(requests)}
