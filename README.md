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
python -m src.backfill --list-history            # just the full-history set and its depths
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

62 of the 74 are in the default sweep. The rest are excluded because they can't be swept
(`manual`, `live`) or because their cost is a different order of magnitude (`per_game`).

**Depth is declared per endpoint too**, via `history` and `min_season`:

| `history` | Depth | Applies to |
|---|---|---|
| `recent` (default) | 2024+ | Everything not listed below — PBP, drives, lines, box scores, per-game fan-outs |
| `full` | Every season the endpoint serves, floored by `min_season` | The 11 ratified season-level endpoints |

`min_season` was probed against the live API on 2026-08-15 rather than assumed, and the
values match the sport's history: 1869 for games/records/teams (the first game ever played),
1936 for rankings (first AP poll), 1967 for draft picks (common draft era).

`--full-history` expands only the ratified set, so a stray flag can't sweep 150 seasons of
every endpoint. Changing that set is one registry line plus one decision-log line — see
`python -m src.backfill --list-history` for the current membership.

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

The loader also maintains **`raw_manifest`**, one row per landed response across every
endpoint, carrying `fetched_at` and a `row_count` computed at load. That single table is
what makes two otherwise-impossible questions answerable:

| Question | Answered by |
|---|---|
| How old is this data? | `mart_data_freshness.last_success_at` — the "data as of X" stamp every page shows |
| Did the pull return anything? | `row_count`, and the `lost_its_data` flag |

**Empty responses are the failure mode this pipeline is most exposed to**: CFBD answers 200
with an empty array, the DAG goes green, and nobody notices until a page is blank. Rather
than guess a per-endpoint row threshold — which needs a season to calibrate and is wrong all
preseason — detection compares each request against *itself*: for an identical
(endpoint, params), did an earlier fetch return rows where the latest returned none?
Legitimately-empty endpoints never trip it, because they never had rows to lose.

That distinction is load-bearing. `records` returned 668 rows for 2024 and 2025 and 0 for
2026, which is a season that hasn't happened, not a regression. Comparing an endpoint's
newest response against its best across *all* params flags every endpoint the moment a new
season opens — the first version of the mart did exactly that and produced 8 false positives.

## Transforms

See [dbt/README.md](dbt/README.md). Short version:

```bash
cp dbt/profiles.yml.example dbt/profiles.yml     # gitignored
cd dbt
DBT_PROFILES_DIR=. dbt build                     # Postgres (default target)
DBT_PROFILES_DIR=. dbt build --target databricks # Databricks
```

### Databricks (M4)

The same models run on both engines; the dialect difference lives entirely in
`dbt/macros/`. Connection settings come from `.env`:

```
DATABRICKS_SERVER_HOSTNAME=<workspace host, no https://>
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>
DATABRICKS_TOKEN=<personal access token>
```

Land raw responses there with the Databricks loader — JSON is stored as `STRING`, since
Delta has no `jsonb`, which is exactly why the macros dispatch:

```bash
python -m src.load_raw_to_databricks teams games --seasons 2024 2025 2026
python -m src.load_raw_to_databricks --all
```

The serverless warehouse auto-starts on first query, so an initial `dbt debug` can take
~30 seconds.

**Known limitation — the token needs the `files` scope.** The intended bulk path is a Unity
Catalog volume upload followed by `COPY INTO`. The Files API currently refuses it:

```
403 {"error_code":403,"message":"Provided access token does not have required scopes: files"}
```

SQL access to the volume works (`LIST` succeeds); only the REST Files API is refused, so
this is a token-scope issue rather than a permissions or networking one. Regenerating the
PAT with the `files` scope would enable the faster path.

Until then the loader goes through SQL, which has a hard ceiling: query text over roughly
16 MB is accepted and 32 MB is rejected outright ("Query text size exceeds limit"). Files
above ~6 MB are therefore split into 4 MB chunks, staged, and reassembled server-side with
`array_sort` over `(seq, chunk)` structs — ordering `collect_list` alone would not
guarantee. Verified byte-identical by md5 on the largest file in the corpus (34 MB,
132,277 records).

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

Local Airflow 3.3.1 (api-server + scheduler + dag-processor, LocalExecutor), reusing the
project Postgres for its own metadata in a separate `airflow` database.

```bash
# one-time: create the metadata database and generate secrets into .env
docker compose exec postgres psql -U cfdb -d cfdb -c "CREATE DATABASE airflow OWNER cfdb;"
python -c "from cryptography.fernet import Fernet; print('AIRFLOW_FERNET_KEY='+Fernet.generate_key().decode())" >> .env
python -c "import secrets; print('AIRFLOW_JWT_SECRET='+secrets.token_hex(32))" >> .env

docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d airflow-init
docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d
open http://localhost:8080
```

Two settings that are easy to get wrong and fail confusingly:

- **`AIRFLOW__CORE__EXECUTION_API_SERVER_URL`** must point at `airflow-apiserver:8080`.
  Workers call back to the API server, and the default is `localhost:8080` — which inside
  a scheduler container is nothing at all. Symptom: tasks queue, then fail with
  `httpx.ConnectError: Connection refused` and no task log.
- **`AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS`**. Airflow 3 defaults to
  SimpleAuthManager, so `airflow users create` no longer works (it needs the FAB auth
  manager). This local stack treats every visitor as admin.

### DAGs

| DAG | Schedule | What |
|---|---|---|
| `cfbd_lines_snapshot` | `@daily` | One `/lines` snapshot of the week currently in play |
| `cfbd_results_refresh` | Sun 12:00 UTC | The week just played + the prior one (late stat corrections), plus ratings and cumulative stats that revise because of it |
| `cfbd_pregame_refresh` | Tue 12:00 UTC | Lines and pre-game win probability for the upcoming week, plus ratings after polls publish |
| `cfbd_alerting_selftest` | manual | Fails on purpose to verify alerting reaches you |

Schedules are **calendar days, not CFBD week boundaries** — CFBD's week 1 spans twelve days
and two Saturdays, so a per-week trigger would sit idle through the opening slate.

Both weekly DAGs drive off the cadence buckets in `src/endpoints.py`, so adding an endpoint
to a bucket puts it in the right refresh automatically. They deliberately force a re-fetch:
the params match earlier requests by design, and staging's latest-file-per-params rule
collapses the overlap.

### Failure alerting

Two channels, wired as `on_failure_callback` on every DAG:

| Channel | Configured via | Behaviour |
|---|---|---|
| Local JSONL | none — always on | Appends to `data/alerts/failures.jsonl` |
| SMTP email | `ALERT_*` in `.env` | Sent only when host/from/to are all set |

```
ALERT_SMTP_HOST=smtp.gmail.com
ALERT_SMTP_PORT=587
ALERT_SMTP_USER=you@gmail.com
ALERT_SMTP_PASSWORD=<App Password>
ALERT_EMAIL_FROM=you@gmail.com
ALERT_EMAIL_TO=you@gmail.com
```

The local file is always written because an alerting channel that needs configuration is
one that's off on the day it's needed. Neither path can raise: an exception in a failure
handler would mask the failure it exists to report.

Raise the lines cadence to hourly by changing `SCHEDULE` in
[dags/lines_snapshot_dag.py](dags/lines_snapshot_dag.py). The snapshot targets one week
(~0.11 MB), so hourly costs ~2.6 MB and 24 calls a day — about 320 MB across a season.
A season-scoped snapshot would be 15x that.

DAGs schedule and retry only. They perform no transforms and compute no metrics: tasks
call functions in `src/`, which land raw responses. Meaning is dbt's job.

## Site (M6, in development)

Streamlit reading marts from serving Postgres. Runs locally against the current marts
while hosting comes online.

```bash
streamlit run site/app.py     # http://localhost:8501
```

Two boundaries the code enforces rather than documents:

- **Read-only by role.** The site connects as `cfdb_read`, which has SELECT and nothing
  else — verified against INSERT/DELETE/CREATE/DROP at creation. A bug in a page cannot
  write to the warehouse.
- **Marts only, no computation.** Every query selects from a `mart_*` table. Sorting,
  filtering and formatting are presentation; a new *number* is a new dbt model, requested
  through the demand-driven process. `site/db.py` is the single place queries live, so this
  is reviewable in one file.

Every page carries a "data as of" stamp (rule #5) sourced from `mart_data_freshness`,
scoped to the endpoints the page actually reads — an hourly lines snapshot must not make a
schedule page look fresher than it is.
