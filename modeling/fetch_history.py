"""Fetch 2016+ history to THIS checkout's `data/raw/` — and nowhere else (cfdb-wtc-R-2481).

    python -m modeling.fetch_history            # print the plan, fetch nothing
    python -m modeling.fetch_history --go       # fetch it

THE BOUNDARY. `src.ingest.fetch` writes the API response to `data/raw/<endpoint>/` relative to the
working directory, plus a file manifest beside it — both gitignored (`.gitignore:19`). It never
touches the warehouse. Nothing here loads what it fetches: the raw loader, dbt and the DAGs are
session A's, and drives landed in the warehouse would reach the site within two hours
(`dags/scores_refresh_dag.py` rebuilds `+srv_drive`). This module is read from disk by
`modeling.disk_source` instead.

THE PLAN comes from the registry's own `backfill.requests_for`. Two gates are lifted IN MEMORY for
the duration of planning, never in the file: `PBP_SEASONS` (which confines drives and plays to
2024+ by Marc's 2026-08-15 decision; his 2026-09-24 "1 - A, 2 - B" widens it for this disk-only
fetch), and `load_latest_raw`, which looks for calendars in a local `data/raw/` this checkout
lacks — calendars are read from `raw.raw_calendar` instead, read-only. `ingest.fetch` is replaced
by a function that raises while planning, so planning can never spend a call.
"""
import argparse
import os
import time
from typing import Dict, List, Tuple

import psycopg2

from src import backfill, ingest
from src.endpoints import BY_PATH

FOUR = ("stats/game/advanced", "stats/game/havoc", "drives", "talent")
FOUR_SEASONS = [str(y) for y in range(2016, 2026)]            # 2016–2025; 2025 and 2024 for parity
PLAYS_SEASONS = [str(y) for y in range(2016, 2024)]          # 2016–2023
CALL_CEILING = 600                                           # the prompt's stop line


def _warehouse():
    return psycopg2.connect(host=os.environ["CFDB_WAREHOUSE_HOST"], port=int(os.environ["CFDB_WAREHOUSE_PORT"]),
                            user=os.environ.get("PG_USER", "cfdb"), password=os.environ.get("PG_PASSWORD", "cfdb"),
                            dbname=os.environ.get("PG_DB", "cfdb"), options="-c default_transaction_read_only=on")


def plan() -> List[Tuple[str, Dict[str, str]]]:
    """Every request, from `requests_for`, with the two gates lifted in memory only."""
    conn = _warehouse()

    def calendar_from_warehouse(endpoint, params):
        assert endpoint == "calendar", endpoint
        cur = conn.cursor()
        cur.execute("select content->'data' from raw.raw_calendar where params->>'year' = %s "
                    "order by fetched_at desc limit 1", (params["year"],))
        row = cur.fetchone()
        return row[0] if row else None

    def no_fetch(*_a, **_k):
        raise RuntimeError("a fetch was attempted while planning — refused")

    saved = (backfill.PBP_SEASONS, backfill.load_latest_raw, backfill.ingest.fetch)
    try:
        backfill.PBP_SEASONS = set(backfill.PBP_SEASONS) | set(FOUR_SEASONS) | set(PLAYS_SEASONS)
        backfill.load_latest_raw = calendar_from_warehouse
        backfill.ingest.fetch = no_fetch
        requests = []
        for path in FOUR:
            requests += backfill.requests_for(BY_PATH[path], FOUR_SEASONS, per_game=False, current_season=2026)
        requests += backfill.requests_for(BY_PATH["plays"], PLAYS_SEASONS, per_game=False, current_season=2026)
    finally:
        backfill.PBP_SEASONS, backfill.load_latest_raw, backfill.ingest.fetch = saved
        conn.close()
    return requests


def run(requests, sleep: float = backfill.SLEEP_SECONDS) -> Dict[str, int]:
    """Fetch each request once, skipping any already on disk; one retry after a failure."""
    counts = {"planned": len(requests), "fetched": 0, "skipped": 0, "retried": 0, "failed": 0}
    for i, (endpoint, params) in enumerate(requests, 1):
        if backfill.already_fetched(endpoint, params):
            counts["skipped"] += 1
            continue
        for attempt in (1, 2):
            try:
                status = ingest.fetch(endpoint, params).status_code
            except Exception as error:          # a network error is one failed request, not the run
                status = type(error).__name__
            if status == 200:
                counts["fetched"] += 1
                break
            if attempt == 1:
                counts["retried"] += 1
                time.sleep(5)
            else:
                counts["failed"] += 1
                print(f"FAILED {status}: {endpoint} {params}", flush=True)
        print(f"[{i}/{len(requests)}] {endpoint} {params}", flush=True)
        time.sleep(sleep)
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--go", action="store_true", help="fetch; without it, print the plan only")
    args = parser.parse_args(argv)
    requests = plan()
    by_endpoint: Dict[str, int] = {}
    for endpoint, _ in requests:
        by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
    print(f"planned {len(requests)} requests: {by_endpoint}", flush=True)
    if len(requests) > CALL_CEILING:
        raise SystemExit(f"refusing: {len(requests)} planned requests exceeds the {CALL_CEILING} ceiling")
    if not args.go:
        return 0
    print(run(requests), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
