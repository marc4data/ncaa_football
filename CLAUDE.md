# CLAUDE.md — Claude Code repo guidance

This file seeds repo-level engineering conventions, commands, and layout for the Claude Code implementation of the cfdb project.

Purpose
- Implementation repository for ingestion, DAGs, dbt, models, and the Streamlit app.

Conventions
- Python 3.11+ for scripts and Airflow workers.
- `src/` contains runnable scripts and packages.
- DBT lives under `dbt/`.
- Tests under `tests/` where applicable.

Key commands
- Local Docker Compose (development): `docker compose up --build`
- Run ingestion (example): `python -m src.ingest fetch teams`
- Historical backfill (idempotent, resumable): `python -m src.backfill --seasons 2024 2025`
- Audit the raw layer after any backfill: `python -m src.validate_raw`
- Install dev tooling: `pip install -r requirements-dev.txt`
- Lint: `flake8 src dags tests` · Tests: `pytest -q`
- CI runs both on every PR to `main` (`.github/workflows/ci.yml`). The live CFBD
  smoke test is a manual `workflow_dispatch` job — unit tests never hit the API.

Secrets
- CFBD API key and other secrets must be stored in CI/GitHub Secrets or a local `.env` that is NOT committed.

Decision log
- Source of truth for architecture/decisions is the Cowork folder's `CLAUDE.md` (outside this repo). Record implementation deviations here.
