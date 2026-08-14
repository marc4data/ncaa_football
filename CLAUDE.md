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
- Run ingestion script (example): `python -m src.ingest_stub`

Secrets
- CFBD API key and other secrets must be stored in CI/GitHub Secrets or a local `.env` that is NOT committed.

Decision log
- Source of truth for architecture/decisions is the Cowork folder's `CLAUDE.md` (outside this repo). Record implementation deviations here.
