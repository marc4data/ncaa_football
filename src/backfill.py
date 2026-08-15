"""Historical backfill: land whole seasons of CFBD data into the raw layer.

Usage:
  python -m src.backfill --list                    # show the endpoint registry
  python -m src.backfill --dry-run                 # show the plan, fetch nothing
  python -m src.backfill                           # sweep every registry endpoint
  python -m src.backfill --seasons 2024 2025 2026
  python -m src.backfill --only plays drives       # restrict to some endpoints
  python -m src.backfill --bucket C1               # restrict to a cadence bucket
  python -m src.backfill --per-game --seasons 2024 # add the per-game fan-out (expensive)
  python -m src.backfill --force                   # re-fetch even if already present

What gets fetched is decided by `src/endpoints.py`, not by this module — see that file for
the registry and the meaning of each strategy.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import ingest
from .endpoints import (
    BY_PATH, HISTORY_FULL, LIVE, MANUAL, PER_GAME, REGISTRY, SEASON, SEASON_TYPE,
    SEASON_WEEK, STATIC, PER_GAME_COST_NOTE, Endpoint, resolve,
)
from .raw_manifest import RawManifest

# Play-by-play and drive detail are scoped to these seasons only, per CLAUDE.md's data scope.
PBP_SEASONS = {"2024", "2025", "2026"}
PBP_ENDPOINTS = {"plays", "plays/stats", "drives"}

DEFAULT_SEASONS = ["2024", "2025"]
SEASON_TYPES = ["regular", "postseason"]

# Be polite to the API between calls; the backfill is not in a hurry.
SLEEP_SECONDS = 0.3

Request = Tuple[str, Dict[str, str]]

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


def completed_game_ids(season: str) -> List[str]:
    """Game ids for a season, read from already-landed /games responses.

    Per-game fan-out depends on the bulk sweep having run first; that ordering is
    deliberate, so the expensive step can never run against a guess.
    """
    ids: List[str] = []
    for season_type in SEASON_TYPES:
        payload = load_latest_raw("games", {"year": season, "seasonType": season_type})
        if not payload:
            continue
        for game in payload:
            if game.get("completed"):
                ids.append(str(game["id"]))
    return ids


def seasons_for(endpoint: Endpoint, seasons: List[str], full_history: bool,
                current_season: int) -> List[str]:
    """Which seasons to pull for one endpoint.

    Under --full-history, endpoints marked HISTORY_FULL ignore the requested season list
    and expand across everything they actually serve, bounded by the min_season probed
    from the live API. Every other endpoint keeps the project's default 2024+ scope, which
    is the point of the attribute: depth is declared per endpoint, not per invocation.
    """
    if full_history and endpoint.history == HISTORY_FULL and endpoint.min_season:
        return [str(y) for y in range(endpoint.min_season, current_season + 1)]
    return seasons


def requests_for(endpoint: Endpoint, seasons: List[str], per_game: bool,
                 full_history: bool = False,
                 current_season: Optional[int] = None) -> List[Request]:
    """Expand one registry entry into concrete (endpoint, params) requests."""
    if endpoint.strategy in (MANUAL, LIVE):
        return []

    if endpoint.strategy == STATIC:
        return [(endpoint.path, {})]

    current_season = current_season or datetime.now(timezone.utc).year
    out: List[Request] = []
    for season in seasons_for(endpoint, seasons, full_history, current_season):
        if endpoint.path in PBP_ENDPOINTS and season not in PBP_SEASONS:
            continue

        if endpoint.strategy == SEASON:
            out.append((endpoint.path, {"year": season}))

        elif endpoint.strategy == SEASON_TYPE:
            for season_type in SEASON_TYPES:
                out.append((endpoint.path, {"year": season, "seasonType": season_type}))

        elif endpoint.strategy == SEASON_WEEK:
            weeks = season_weeks(season)
            for season_type in SEASON_TYPES:
                for week in weeks[season_type]:
                    out.append((endpoint.path,
                                {"year": season, "week": week, "seasonType": season_type}))

        elif endpoint.strategy == PER_GAME:
            if not per_game:
                continue
            id_param = endpoint.extra.get("id_param", "id")
            for game_id in completed_game_ids(season):
                out.append((endpoint.path, {id_param: game_id}))

    return out


def build_plan(seasons: List[str], only: List[str] | None, bucket: str | None,
               per_game: bool, full_history: bool = False,
               current_season: Optional[int] = None) -> List[Request]:
    """The full list of (endpoint, params) the backfill intends to fetch."""
    selected = resolve(only) if only else [e for e in REGISTRY if e.include]
    if bucket:
        selected = [e for e in selected if e.bucket == bucket]
    if per_game and not only:
        selected = selected + [e for e in REGISTRY if e.strategy == PER_GAME and not e.include]

    if full_history:
        # --full-history is about depth, not breadth: restrict to the ratified set so a
        # stray flag can't sweep 150 seasons of every endpoint.
        selected = [e for e in selected if e.history == HISTORY_FULL]

    plan: List[Request] = []
    for endpoint in selected:
        plan.extend(requests_for(endpoint, seasons, per_game, full_history, current_season))
    return plan


def run(seasons: List[str], only: List[str] | None, bucket: str | None, per_game: bool,
        force: bool, dry_run: bool, snapshot: bool = False,
        full_history: bool = False) -> int:
    plan = build_plan(seasons, only, bucket, per_game, full_history)
    print(f"Backfill plan: {len(plan)} requests across seasons {', '.join(seasons)}")

    fetched = skipped = failed = 0
    failures: List[str] = []

    for endpoint, params in plan:
        label = f"{endpoint} {params}"
        # Snapshot endpoints are re-fetched on purpose under --snapshot: the same request
        # answers differently over time, and that difference is the data.
        resnapshot = snapshot and BY_PATH[endpoint].snapshot
        if not force and not resnapshot and already_fetched(endpoint, params):
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


def list_registry(history_only: bool = False) -> int:
    """Print the registry as a table — the readable view of what the code declares."""
    rows = [e for e in REGISTRY if not history_only or e.history == HISTORY_FULL]

    print(f"{'endpoint':28} {'strategy':12} {'bucket':7} {'history':8} {'depth':11} {'swept':6} note")
    print("-" * 110)
    for e in rows:
        depth = f"{e.min_season}+" if e.min_season else ("2024+" if e.include else "-")
        print(f"{e.path:28} {e.strategy:12} {e.bucket:7} {e.history:8} {depth:11} "
              f"{str(e.include):6} {e.note}")

    full = [e for e in REGISTRY if e.history == HISTORY_FULL]
    print(f"\n{len(rows)} shown. Registry: {len(REGISTRY)} endpoints, "
          f"{len([e for e in REGISTRY if e.include])} in the default sweep, "
          f"{len(full)} ratified for full history.")
    print("\nDepth is declared per endpoint, not per invocation:")
    print("  recent  the project default, 2024+ (CLAUDE.md data scope)")
    print("  full    every season the endpoint serves, floored by min_season — probed")
    print("          against the live API 2026-08-15, not assumed. Run with --full-history.")
    print("\nChanging the full-history set is one registry line plus one decision-log line.")
    if not history_only:
        print(f"\n{PER_GAME_COST_NOTE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill historical CFBD seasons into the raw layer.")
    parser.add_argument("--seasons", nargs="+", default=DEFAULT_SEASONS)
    parser.add_argument("--only", nargs="+", help="restrict to these endpoints")
    parser.add_argument("--bucket", help="restrict to a cadence bucket (A, B, C1, C2, D, REF)")
    parser.add_argument("--per-game", action="store_true",
                        help="include per-game fan-out endpoints (expensive)")
    parser.add_argument("--force", action="store_true", help="re-fetch even if already present")
    parser.add_argument("--snapshot", action="store_true",
                        help="re-fetch snapshot endpoints (lines, pregame wp) even if present")
    parser.add_argument("--full-history", action="store_true",
                        help="for the ratified full-history endpoints, pull every season "
                             "they serve rather than the --seasons list")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without fetching")
    parser.add_argument("--list", action="store_true", help="print the endpoint registry and exit")
    parser.add_argument("--list-history", action="store_true",
                        help="print only the endpoints ratified for full history")
    args = parser.parse_args()

    if args.list or args.list_history:
        return list_registry(history_only=args.list_history)
    return run(args.seasons, args.only, args.bucket, args.per_game, args.force, args.dry_run,
               args.snapshot, args.full_history)


if __name__ == "__main__":
    sys.exit(main())
