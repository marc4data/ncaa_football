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

Key commands
- Local Docker Compose (development): `docker compose up --build`
- Run ingestion (example): `python -m src.ingest fetch teams`
- Historical backfill (idempotent, resumable): `python -m src.backfill --seasons 2024 2025`
- Curated deep history: `python -m src.backfill --full-history`
- Audit the raw layer after any backfill: `python -m src.validate_raw`
- Install dev tooling: `pip install -r requirements-dev.txt`
- Lint: `flake8 src dags tests` · Tests: `pytest -q`
- CI runs both on every PR to `main` (`.github/workflows/ci.yml`). The live CFBD
  smoke test is a manual `workflow_dispatch` job — unit tests never hit the API.

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