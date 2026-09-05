# CLAUDE.md — Claude Code repo guidance

This file seeds repo-level engineering conventions, commands, and layout for the Claude Code implementation of the cfdb project.

Purpose
- Implementation repository for ingestion, DAGs, dbt, models, and the Streamlit app.

Conventions
- Python 3.11+ for scripts and Airflow workers.
- `src/` contains runnable scripts and packages.
- DBT lives under `dbt/`.
- Tests under `tests/` where applicable.

Data scope (synced with Cowork `CLAUDE.md`, 2026-08-15)
- **Depth is declared per endpoint in `src/endpoints.py`, not per invocation.** The `history`
  attribute is the operative source of truth; `min_season` records the earliest season each
  endpoint actually serves, probed against the live API rather than assumed.
- **`recent` (default): 2024+.** Play-by-play, drives, lines, box scores, and the per-game
  fan-outs all stay here.
- **`full`: every season the endpoint serves.** The ratified set is games, records, rankings,
  teams, coaches, stats/season, stats/season/advanced, stats/player/season, wepa/team/season,
  ppa/players/season, and draft/*. Amending it is one registry line plus one decision-log line
  — never a code change elsewhere.
- **The current season's framework lands as soon as the season exists**: schedule, rosters,
  coaches, rankings, and season-scoped teams, before Week 1 and regardless of whether any game
  has been played.

Environments
------------
⚠️ **THERE IS NO LOCAL WAREHOUSE, AND THERE IS NOT GOING TO BE ONE.** The laptop Postgres was
dropped on 2026-09-05 (R-296). This section replaces the line that used to sit under Key
commands — *"Local Docker Compose (development): `docker compose up --build`"* — which is
what a fresh session read, believed, and acted on.

**Three databases. Two of them are real and they are not the same one.**

| Instance | Where | Holds | Written by |
|---|---|---|---|
| **Warehouse** (transform) | droplet, pipeline stack `/opt/cfdb-pipeline` — `docker-compose.yml` + `docker-compose.airflow.yml` merged, `PG_HOST=postgres`, `PG_DB=cfdb` | `raw`, `staging`, `marts`, `serving` — **dbt builds here** | Airflow → dbt; the `src/` loaders |
| **Serving** | droplet, serving stack `/opt/cfdb` — `deploy/docker-compose.yml`, bound `127.0.0.1:5433` | the published subset the site reads | `src/publish_marts.py` only |
| ~~Local Postgres~~ | ~~laptop~~ | **DROPPED 2026-09-05, R-296** | nobody |

The distinction is the whole point. A question answered against serving sees only what has
been *published*; the same question against the warehouse sees what has been *built*. Both
answer. Neither errors. **"There is no warehouse to build against" was concluded on
2026-09-05 from the serving instance — a true fact about the wrong object.**

⚠️ **`docker-compose.yml` at the repo root is NOT a local dev database.** It defines the
`postgres` service that `docker-compose.airflow.yml` depends on and connects to — i.e. it is
the *warehouse's* definition, deployed to the droplet. Running it on a laptop stands up a
second database with the same name on the same port, which is exactly how a dbt build
succeeds against nothing anyone meant.

**Reaching the warehouse**

```bash
scripts/warehouse_tunnel.sh          # another terminal; leave it running
python scripts/preflight_env.py      # prints working copy, profile, target, host, database
```

This is a **read-and-build** path, not a deploy path, and the difference is structural rather
than promised: the tunnel forwards one port and runs no remote command. Changing what the
site shows is still `scripts/deploy_main.sh` and still nothing else — see `deploy/README.md`,
which removed the manual deploy commands deliberately.

**The two files git cannot fix for you**

`dbt/profiles.yml` (.gitignore line 14) and `.env` (line 7) are untracked, so they are **per
working copy and hand-copied**, and this repo now has three working copies side by side:

    ncaa_football/claude_code/     main + in-flight branches
    ncaa_football/wt-drives/       worktree, feature work
    ncaa_football/cfdb_deploy/     worktree pinned to main; Airflow's mounts point here

Merging a fix to the template changes **nothing** in any of them until someone re-copies it.
On 2026-09-05 one working copy's root had *no* `dbt/profiles.yml` at all while its own
worktree had one pointing at `localhost:5432`. Two directories of one repository, in
different states, neither visible to the other. `scripts/preflight_env.py` and the
`on-run-start` hook in `dbt/dbt_project.yml` exist so that the next such copy says so on the
**first** dbt command rather than the twelfth model.

**Resync after the environment fix merges (R-317)**

    1. The environment fix merges to main.
    2. EVERY working copy fetches and rebases:
         claude_code/ (and its in-flight branch)    wt-drives/    cfdb_deploy/
    3. EVERY working copy, BY HAND, because git cannot do it:
         cp dbt/profiles.yml.example dbt/profiles.yml
         cp .env.example .env   (or diff an existing .env against it) and fill the values
         delete the retired CFDB_DROPLET_PG_ADDR and CFDB_REMOTE_PG_PORT from .env
    4. EVERY working copy runs `python scripts/preflight_env.py`. It must pass in each, and
       CI must stay green — the workflow runs the same check.
    5. Only then does feature work resume.

⚠️ **Step 3 is the one that will be skipped.** That is precisely why step 4 exists: if it is
skipped, step 4 fails loudly and says which working copy and which file.

Key commands
- Reach the warehouse: `scripts/warehouse_tunnel.sh` then `python scripts/preflight_env.py`
- Run ingestion (example): `python -m src.ingest fetch teams`
- Historical backfill (idempotent, resumable): `python -m src.backfill --seasons 2024 2025`
- Curated deep history: `python -m src.backfill --full-history`
- Audit the raw layer after any backfill: `python -m src.validate_raw`
- Install dev tooling: `pip install -r requirements-dev.txt`
- Lint: `flake8 src dags tests` · Tests: `pytest -q`
- CI runs both on every PR to `main` (`.github/workflows/ci.yml`). The live CFBD
  smoke test is a manual `workflow_dispatch` job — unit tests never hit the API.

Deploying and publishing are SINGLE-FLIGHT, and it is a mechanism now (R-314)
- `scripts/deploy_main.sh` and `python -m src.publish_marts` are executable in **every**
  working copy, and there are three. *"Only one session publishes"* was a sentence in a
  prompt, and a prompt is not what runs.
- The deploy takes a lock **on the droplet** (`/opt/cfdb/locks/deploy.lock`, atomic `mkdir`,
  released on exit) — remote because the resource is remote, and a laptop lockfile would do
  nothing about a second machine. The publish takes a **Postgres advisory lock** on the
  warehouse, because the publish identity is a forced command that cannot run `mkdir`, and
  because an advisory lock dies with its connection and so can never go stale.
- **Both refuse loudly and neither queues.** A second deploy would run against a tree the
  first one moved underneath it; a second publish would ship a warehouse the first has
  already rebuilt.

Licensed material — NEVER COMMIT
- `cfdb_model_pack/` is the CFB Model Training Pack (2026 Edition, Rad Sports Analytics).
  Its LICENSE is **personal, non-commercial, original-purchaser-only** and explicitly
  prohibits uploading the pack to a repository or sharing it with non-purchasers. The
  notebooks, `training_data.csv` and guides ARE the licensed material; the `.zip` is only
  the wrapper, so ignoring `*.zip` alone is not sufficient.
- `cfdb_model_pack/`, `model_outputs/` and `*.zip` are gitignored. Verified clean: no pack
  file has ever been tracked, committed on any branch, or left in the object store.
- This repo is private today and going public has been discussed. **A later .gitignore does
  not remove anything from git history** — if a pack file is ever committed, stop and raise
  it rather than fixing it in passing.
- Predictions derived from the pack must be attributed as cfdb's own, built on a licensed
  training pack, and never presented as official CollegeFootballData.com predictions. The
  wording lives in `dim_model_version.attribution` and `srv_model_performance.attribution`
  so a page cannot render the numbers without it.

Secrets
- CFBD API key and other secrets must be stored in CI/GitHub Secrets or a local `.env` that is NOT committed.

Decision log
- Source of truth for architecture/decisions is the Cowork folder's `CLAUDE.md` (outside this repo). Record implementation deviations here.

## cfdb — standing context

Division of labour ("church vs state"):
- Strategy, decisions and design docs live in ../claude_work. That folder is the source of
  truth for WHAT to build and WHY. Do not put production code there.
- All code lives in this repo. You implement within decisions already made; you do not
  re-litigate them. If a decision looks wrong, SAY SO and stop — do not quietly do something
  else.

Authoritative documents (read before acting, in ../claude_work):
- CLAUDE.md ................................ project rules
- decision_log.md .......................... settled decisions, newest last
- roadmap.md ............................... phasing
- cfdb_page_to_mart_matrix.xlsx ............ the dimensional model (7 sheets)
- cfdb_wireframe_v02.html .................. the 17 site screens this model serves
- cfdb_site_ia_and_layouts.md .............. IA rationale + CFBD endpoint coverage

Settled decisions you must work within:
- Naming: fct_* / dim_* in the warehouse. Serving layer is pre-joined wide srv_* tables.
- Streamlit is display-only: single-table SELECT + WHERE. No joins, no metric math in the app.
- dbt owns all transforms, metric definitions and tests. Airflow owns reliability only —
  no business logic in DAGs.
- Scope: FBS spine. Non-FBS teams that play an FBS opponent exist as dim_team stubs
  (name, conference, logo, is_fbs = false) with no deep stats.
- Play-by-play scope: 2024, 2025, 2026 only.
- CFBD API keys are server-side only, never client-side, never committed.

IMPORTANT — how much to trust the matrix:
cfdb_page_to_mart_matrix.xlsx is a PROPOSAL. It was written from three object names
(mart_data_freshness, mart_team_schedule, mart_team_season_record) with no schema inspected,
and from CFBD's public docs with no live API calls. Rows marked ASSUMED or PARTIAL are
inferences. Verify before you build on them, and report anything that contradicts the doc
rather than silently conforming to it.
```