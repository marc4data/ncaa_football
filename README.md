# cfdb — college football data platform

Implementation code for the cfdb project: ingestion, Airflow DAGs, dbt transforms, ML
scripts, and the Streamlit app. Architecture and decisions live in the Cowork folder's
`CLAUDE.md`; this repo covers *how*.

Pipeline: **CFBD API → immutable raw JSON → Postgres → dbt (staging → marts)**.

## Setup

```bash
docker compose up -d postgres                    # local warehouse/serving Postgres
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt              # includes runtime deps + pytest/flake8
```

Create `.env` (never committed):

```
CFBD_API_KEY=<your key>
DATABRICKS_HOST=<workspace URL>
DATABRICKS_TOKEN=<token>
```

## Ingestion

Single endpoint:

```bash
python -m src.ingest fetch teams
python -m src.ingest fetch games --year 2024 --seasonType regular
python -m src.ingest fetch plays --year 2024 --week 1 --seasonType regular
```

Every response lands immutably under `data/raw/<endpoint>/<utc-timestamp>.json` alongside
a `manifest.json` recording filename, params, status code, and fetch time. Failed fetches
are landed too — the raw layer records what happened, and staging filters to `status_code = 200`.

### Historical backfill

```bash
python -m src.backfill --list                    # the endpoint registry
python -m src.backfill --dry-run                 # show the plan, fetch nothing
python -m src.backfill --seasons 2024 2025       # full-breadth sweep
python -m src.backfill --only plays drives       # restrict to some endpoints
python -m src.backfill --bucket C1               # restrict to a cadence bucket
python -m src.backfill --per-game --seasons 2024 # add per-game fan-out (expensive)
python -m src.backfill --force                   # re-fetch even if already present
python -m src.backfill --snapshot --only lines --seasons 2026   # daily lines snapshot
```

**Snapshot endpoints.** `/lines` and `/metrics/wp/pregame` answer differently to the *same*
request over time — that difference is the data. They're marked `snapshot=True` in the
registry, and `--snapshot` bypasses skip-if-present for them only. Without it the daily
lines pull would be skipped from its second run onward and no movement series would
accumulate. A plain backfill rerun stays a no-op.

**What gets fetched lives in [`src/endpoints.py`](src/endpoints.py), not in the backfill.**
That registry covers all 74 endpoints in the CFBD OpenAPI spec (v5.24.0), each tagged with
a fetch strategy and a cadence bucket:

| Strategy | Meaning | Cost |
|---|---|---|
| `static` | no parameters — one call, ever | 1 |
| `season` | one call per season | 1/season |
| `season_type` | per (season, seasonType) — regular and postseason | 2/season |
| `season_week` | per (season, seasonType, week) — the volume drivers | ~17/season |
| `per_game` | one call per game id — **opt-in**, ~3,800/season | large |
| `manual` | needs an argument a sweep can't invent (playerId, searchTerm) | n/a |
| `live` | only meaningful mid-game, or API metadata | n/a |

63 of the 74 are in the default sweep. The rest are excluded because they can't be swept
(`manual`, `live`) or because their cost is a different order of magnitude (`per_game`).

Per-game fan-out reads game ids from **already-landed** `/games` responses, so the
expensive step can never run against a guess — run the bulk sweep first.

Check quota before a large run: `curl -H "Authorization: Bearer $CFBD_API_KEY" \
https://api.collegefootballdata.com/info` reports tier, monthly limit, and calls remaining.

**The backfill is idempotent and resumable.** A request is identified by (endpoint, params);
if the manifest already has a successful entry for that pair, the call is skipped. Re-running
after a partial run fills only the gaps, and re-running a complete backfill fetches nothing.
Week numbers come from CFBD's `/calendar`, not a hardcoded count — season length varies.

Failed fetches are *not* treated as done, so a gap is always refilled on the next run. A run
with any failure exits non-zero.

### Auditing the raw layer

```bash
python -m src.validate_raw                       # audit; non-zero exit if anything is wrong
python -m src.validate_raw --repair              # delete mismatched files + manifest entries
```

Raw files are self-describing — each stores the params of the request that produced it — so
the manifest is checked against the data rather than trusted. Detects three problems:
mismatched params (a file overwritten by a different request), missing files, and orphans.

**Run this after any backfill.** It exists because second-resolution filenames once collided
during a fast run, silently overwriting 6 files and leaving them labelled with the wrong
request's params. Filenames now carry milliseconds and never overwrite, and this audit is
the standing check.

Repair deliberately doesn't re-fetch: it removes the bad entries, and the next
`python -m src.backfill` refills the gaps through its normal skip-if-present logic.

## Loading to Postgres

```bash
python -m src.load_raw_to_postgres teams      # one endpoint
python -m src.load_raw_to_postgres --all      # every endpoint landed under data/raw
```

One row per raw file in `raw_<endpoint>`, with the response as `jsonb`. Loads are upserts
keyed on filename, so re-running never duplicates.

Two timestamps, deliberately distinct: **`fetched_at`** is when the response was observed
(from the manifest) and **`added_at`** is when it was loaded. Snapshot analysis needs the
former — line movement is only interpretable against observation time.

## Transforms

See [dbt/README.md](dbt/README.md). Short version:

```bash
cp dbt/profiles.yml.example dbt/profiles.yml     # gitignored
cd dbt
DBT_PROFILES_DIR=. dbt run
DBT_PROFILES_DIR=. dbt test
```

## Full rebuild from scratch

```bash
docker compose up -d postgres
python -m src.backfill --seasons 2024 2025
python -m src.validate_raw
python -m src.load_raw_to_postgres --all
cd dbt && DBT_PROFILES_DIR=. dbt run && DBT_PROFILES_DIR=. dbt test
```

Raw is never mutated, so this rebuilds every downstream table from data already on disk —
no re-fetching unless the raw layer has gaps.

## Tests and CI

```bash
flake8 src dags tests
pytest -q
```

CI runs both on every PR to `main`, plus guards asserting no secrets and no `data/` files
are ever tracked. The live CFBD smoke test is a manual `workflow_dispatch` job — unit tests
stub the network and never hit the API.

## Airflow

`docker-compose.airflow.yml` is a template for a local webserver + scheduler. Generate a
real `AIRFLOW__CORE__FERNET_KEY` into `.env` before running it — the committed value is a
placeholder.
