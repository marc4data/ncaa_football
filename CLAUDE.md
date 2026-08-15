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

Secrets
- CFBD API key and other secrets must be stored in CI/GitHub Secrets or a local `.env` that is NOT committed.

Decision log
- Source of truth for architecture/decisions is the Cowork folder's `CLAUDE.md` (outside this repo). Record implementation deviations here.
