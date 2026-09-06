# cfdb — college football data platform

A college football analytics platform: **CFBD API → immutable raw JSON → Postgres → dbt
(staging → marts → serving) → a Streamlit site behind Cloudflare Access.** 110,634 games
back to 1869, seventeen pre-joined serving views, and model predictions built on a licensed
feature store.

> ### 📄 Start with [`docs/README.md`](docs/README.md)
>
> The code is the easy half. `docs/` holds the decision log, 215 numbered acceptance
> criteria, the licence boundary reasoned in writing before anything was built, and
> twenty-four rounds of the prompts that drove the work — including the decisions that were
> wrong and what changed. That is the part worth reading first.

## First: install the git hooks

```bash
bash scripts/install_hooks.sh
```

`.git/hooks` is not version controlled, so this is per-clone. The pre-commit hook refuses
any staged path under `cfdb_model_pack/` — that directory holds commercially licensed
material whose terms prohibit publishing it to a public repository, and this repository is
public. See [`docs/publication_boundary.md`](docs/publication_boundary.md).

## Setup

**There is no local warehouse.** The pipeline runs on the droplet: dbt builds into the
warehouse Postgres in the pipeline stack, and the site reads a published subset from a
second, separate serving Postgres. The laptop Postgres this README used to open with
(`docker compose up -d postgres`) was decommissioned on 2026-09-05 and is not coming back —
running it stood up a second database with the same name on the same port, which is how a
green dbt build could mean nothing. See **Environments** in `CLAUDE.md`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt              # runtime deps + pytest/flake8

cp .env.example .env                             # then fill it in — key names and comments only
cp dbt/profiles.yml.example dbt/profiles.yml      # gitignored, so PER WORKING COPY

scripts/warehouse_tunnel.sh                      # another terminal; leave it running
python scripts/preflight_env.py                  # says which database you just reached
```

Both files you copied are gitignored, so a `git pull` can never correct them and each
working copy has its own. That is what `scripts/preflight_env.py` is for: run it after
copying, and it tells you which working copy, which profile file and which database — and
fails distinctly for *no profile here* versus *a profile pointing at the database that was
dropped*.

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

## Layers

Schema per layer in both engines (decision log 2026-08-17), rather than a naming convention
in one namespace:

| Layer | Postgres | Databricks | Written by |
|---|---|---|---|
| raw | `raw.*` | `workspace.raw.*` | the loaders |
| staging | `staging.*` | `workspace.staging.*` | dbt |
| marts | `marts.*` | `workspace.marts.*` | dbt |

`dbt/macros/generate_schema_name.sql` returns the configured schema verbatim; dbt's default
would have produced `public_marts` and kept the layers entangled in the name.

**The serving database is the enforced tier.** It holds published marts only — raw and
staging never ship to the droplet — and `cfdb_read` has USAGE on `marts` and nothing else,
with `search_path = marts` so the site's SQL needs no prefixes. Verified by attempting the
denials rather than assuming them:

```
create table public.x(i int)   -> ERROR: permission denied for schema public
create schema raw              -> ERROR: permission denied for database cfdb
insert into marts.mart_...     -> ERROR: permission denied for table
drop table marts.mart_...      -> ERROR: must be owner of table
```

`ci/check_layering.py` closes the remaining gap: schemas separate each layer's *output*,
but nothing stops a mart selecting straight from raw. That reads dbt's compiled dependency
graph and fails the build if any non-staging model references a source.

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

Against the warehouse, through the tunnel — there is nowhere else to rebuild to.

```bash
scripts/warehouse_tunnel.sh          # another terminal; leave running
python scripts/preflight_env.py      # confirm which database before writing to it

python -m src.backfill --seasons 2024 2025
python -m src.validate_raw
python -m src.load_raw_to_postgres --all
cd dbt && dbt run && dbt test
```

`DBT_PROFILES_DIR=.` is no longer needed: `dbt/profiles.yml` is where dbt looks by default
when run from `dbt/`, and every dbt invocation now prints the target, host and database it
resolved before it builds anything.

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

Airflow 3.3.1 (api-server + scheduler + dag-processor, LocalExecutor) **on the droplet**, at
`/opt/cfdb-pipeline`. It shares the warehouse Postgres for its own metadata in a separate
`airflow` database, and it reads code from a git worktree pinned to `main` — never a working
tree. Deploying it is `scripts/deploy_main.sh` and nothing else; see `deploy/README.md` for
why the individual commands are not reproduced.

The UI is on the droplet's port 8080 and is not published. Reach it over a forward:

```bash
ssh -N -L 8080:127.0.0.1:8080 $CFDB_DROPLET_HOST    # then http://localhost:8080
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

#### Triage: making the alert readable

A traceback answers "what threw". It does not answer what broke, whether it matters, or
what to do. When `ANTHROPIC_API_KEY` is set, [src/alert_triage.py](src/alert_triage.py)
asks Claude those three questions and leads the email with the answers:

```
Subject: [cfdb] FAILURE - Cadence config missing from the Airflow bind mount

WHAT HAPPENED / IMPACT / LIKELY FIX
...
========================================================================
TECHNICAL DETAIL
<every field, then the full traceback>
```

The subject is always `[cfdb] FAILURE - ` so the whole set filters and sorts together.

```
ANTHROPIC_API_KEY=sk-ant-...
ALERT_TRIAGE_MODEL=claude-sonnet-5   # optional
ALERT_TRIAGE_TIMEOUT=25              # optional, seconds
```

Preview it against a real recorded failure without waiting for the next one:

```bash
python -m src.alert_triage --latest     # triage the most recent failure and print the email
python -m src.alert_triage --dry-run    # show the prompt, call nothing
python -m src.alert_triage --index 3    # any earlier failure
```

Three properties this had to have, all of them consequences of running inside the failure
path:

- **It cannot suppress an alert.** Every path returns `None` instead of raising, the caller
  wraps the call anyway, and the plain email goes out unchanged. A summariser that costs us
  an alert is worse than no summariser.
- **It adds no dependency.** The call is `urllib` from the standard library, not the SDK: a
  broken or conflicting install here would take out alerting itself.
- **Secrets never leave the machine.** Known secret *values* — not just variable names — are
  stripped from the error and traceback first, along with URL credentials and bearer tokens,
  because this is the one place the pipeline sends error text to a third party.

Cost is negligible: one short call per failed task, and only on failure.

Raise the lines cadence to hourly by changing `SCHEDULE` in
[dags/lines_snapshot_dag.py](dags/lines_snapshot_dag.py). The snapshot targets one week
(~0.11 MB), so hourly costs ~2.6 MB and 24 calls a day — about 320 MB across a season.
A season-scoped snapshot would be 15x that.

DAGs schedule and retry only. They perform no transforms and compute no metrics: tasks
call functions in `src/`, which land raw responses. Meaning is dbt's job.

## Site (M6, in development)

Streamlit reading the serving Postgres. It runs in production on the droplet behind a
Cloudflare Tunnel and Cloudflare Access; `deploy/README.md` has the deployment.

Running the site locally is still supported and still useful — it is a *reader*, so it needs
a connection to the serving database and creates nothing. Point `SERVING_PG_HOST` at the
local end of a forward to the droplet's serving Postgres (`127.0.0.1:5433` there; a
different instance from the warehouse):

```bash
ssh -N -L 15434:127.0.0.1:5433 $CFDB_DROPLET_HOST   # another terminal
SERVING_PG_HOST=127.0.0.1 SERVING_PG_PORT=15434 streamlit run site/app.py
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
