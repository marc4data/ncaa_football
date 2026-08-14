# Claude Code — cfdb (scaffold)

This repository contains the implementation code for the cfdb project: ingestion scripts, Airflow DAGs, dbt transforms, ML scripts, and the Streamlit app.

Quickstart (local)

1. Copy secrets into a local `.env` (DO NOT COMMIT):

```bash
# .env (example)
CFBD_API_KEY=your_api_key_here
```

2. Start local Postgres for development:

```bash
cd claude_code
docker compose up -d postgres
```

3. Run the ingestion stub:

```bash
CFBD_API_KEY=your_api_key python -m src.ingest fetch teams
```

DBT

- Copy `dbt/profiles.yml.example` to your `~/.dbt/profiles.yml` or set the `DBT_PROFILES_DIR` env var. Then run:

```bash
cd claude_code/dbt
dbt deps
dbt run
```

Airflow (local template)

- See `docker-compose.airflow.yml` for a template to run a local Airflow webserver + scheduler. You'll need to create an `airflow` database in Postgres and initialize the Airflow DB before starting the containers.


Next steps
- Add `dbt/` project and seed models.
- Add `dags/` with Airflow DAG definitions and a `docker-compose.yml` extension for Airflow when ready.
