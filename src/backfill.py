"""Historical backfill: land whole seasons of CFBD data into the raw layer.

Usage:
  python -m src.backfill --dry-run                 # show the plan, fetch nothing
  python -m src.backfill                           # backfill the default seasons
  python -m src.backfill --seasons 2024 2025 2026
  python -m src.backfill --only plays drives       # restrict to some endpoints
  python -m src.backfill --force                   # re-fetch even if already present

Idempotency (M1 open question #4, decided here): **the raw manifest owns "have I already
fetched this?"** A request is identified by (endpoint, params); if the manifest has an
entry for that pair with a 2xx status, the call is skipped. Airflow owns *scheduling* —
when to run — and never duplicates this data state. That keeps re-running the backfill
free, and means a half-finished run resumes rather than restarts.

Weeks come from CFBD's own `/calendar`, not a hardcoded count — season length varies
(2024 had 16 regular weeks, 2026 has 15).
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import ingest
from .raw_manifest import RawManifest

# Play-by-play and drives are scoped to these seasons only, per CLAUDE.md's data scope.
PBP_SEASONS = {"2024", "2025", "2026"}
DEFAULT_SEASONS = ["2024", "2025"]

# Endpoints with no season dimension at all — fetched once.
STATIC_ENDPOINTS = ["conferences", "venues"]

# One call per (season). CFBD serves a whole season in a single response.
SEASON_ENDPOINTS = ["teams", "games", "drives"]

# One call per (season, week, seasonType). These are the volume drivers.
WEEKLY_ENDPOINTS = ["plays", "games/teams"]

SEASON_TYPES = ["regular", "postseason"]

# Be polite to the API between calls; the backfill is not in a hurry.
SLEEP_SECONDS = 0.3

manifest = RawManifest()


def endpoint_key(endpoint: str) -> str:
    """Directory/manifest key for an endpoint — mirrors src.ingest."""
    return endpoint.replace("/", "_")


def already_fetched(endpoint: str, params: Dict[str, Any]) -> bool:
    """True if a successful fetch with exactly these params is already on disk."""
    for entry in manifest.list_entries(endpoint_key(endpoint)):
        if entry.get("params") == params and 200 <= int(entry.get("status_code", 0)) < 300:
            return True
    return False


def load_latest_raw(endpoint: str, params: Dict[str, Any]) -> Any | None:
    """Read the payload of the newest successful raw file for (endpoint, params).

    Lets planning reuse what's already landed instead of re-hitting the API — which is
    what makes `--dry-run` free of side effects on a second run.
    """
    key = endpoint_key(endpoint)
    matches = [
        e for e in manifest.list_entries(key)
        if e.get("params") == params and 200 <= int(e.get("status_code", 0)) < 300
    ]
    if not matches:
        return None
    newest = max(matches, key=lambda e: e["filename"])
    path = Path("data") / "raw" / key / newest["filename"]
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("data")


def season_weeks(season: str) -> Dict[str, List[str]]:
    """Week numbers per season type, from CFBD's own calendar.

    Uses a previously landed calendar when there is one; the calendar for a completed
    season never changes, and planning shouldn't spend API calls to re-learn it.
    """
    params = {"year": season}
    payload = load_latest_raw("calendar", params)
    if payload is None:
        resp = ingest.fetch("calendar", params)
        if resp.status_code != 200:
            raise RuntimeError(f"calendar fetch for {season} returned {resp.status_code}")
        payload = resp.json()

    weeks: Dict[str, List[str]] = {t: [] for t in SEASON_TYPES}
    for entry in payload:
        st = entry.get("seasonType")
        if st in weeks:
            weeks[st].append(str(entry["week"]))
    return weeks


def build_plan(seasons: List[str], only: List[str] | None) -> List[Tuple[str, Dict[str, str]]]:
    """The full list of (endpoint, params) the backfill intends to fetch."""
    plan: List[Tuple[str, Dict[str, str]]] = []

    def wanted(ep: str) -> bool:
        return not only or ep in only

    for ep in STATIC_ENDPOINTS:
        if wanted(ep):
            plan.append((ep, {}))

    for season in seasons:
        for ep in SEASON_ENDPOINTS:
            if not wanted(ep):
                continue
            if ep == "drives" and season not in PBP_SEASONS:
                continue
            if ep == "teams":
                # No seasonType dimension; the roster of teams is a season fact.
                plan.append((ep, {"year": season}))
            else:
                for st in SEASON_TYPES:
                    plan.append((ep, {"year": season, "seasonType": st}))

        if not any(wanted(ep) for ep in WEEKLY_ENDPOINTS):
            continue

        weeks = season_weeks(season)
        for ep in WEEKLY_ENDPOINTS:
            if not wanted(ep):
                continue
            if ep == "plays" and season not in PBP_SEASONS:
                continue
            for st in SEASON_TYPES:
                for week in weeks[st]:
                    plan.append((ep, {"year": season, "week": week, "seasonType": st}))

    return plan


def run(seasons: List[str], only: List[str] | None, force: bool, dry_run: bool) -> int:
    plan = build_plan(seasons, only)
    print(f"Backfill plan: {len(plan)} requests across seasons {', '.join(seasons)}")

    fetched = skipped = failed = 0
    failures: List[str] = []

    for endpoint, params in plan:
        label = f"{endpoint} {params}"
        if not force and already_fetched(endpoint, params):
            skipped += 1
            if dry_run:
                print(f"  SKIP (present)  {label}")
            continue

        if dry_run:
            print(f"  FETCH           {label}")
            fetched += 1
            continue

        resp = ingest.fetch(endpoint, params)
        if resp.status_code == 200:
            fetched += 1
        else:
            failed += 1
            failures.append(f"{label} -> {resp.status_code}")
            print(f"  FAILED {resp.status_code}  {label}")
        time.sleep(SLEEP_SECONDS)

    verb = "would fetch" if dry_run else "fetched"
    print(f"\nDone. {verb}={fetched} skipped={skipped} failed={failed}")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  {f}")
    # Failures are loud: a partial backfill must not look like a success.
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill historical CFBD seasons into the raw layer.")
    parser.add_argument("--seasons", nargs="+", default=DEFAULT_SEASONS)
    parser.add_argument("--only", nargs="+", help="restrict to these endpoints")
    parser.add_argument("--force", action="store_true", help="re-fetch even if already present")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without fetching")
    args = parser.parse_args()
    return run(args.seasons, args.only, args.force, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
