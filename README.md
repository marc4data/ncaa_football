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
python -m src.ingest_stub
```

Next steps
- Add `dbt/` project and seed models.
- Add `dags/` with Airflow DAG definitions and a `docker-compose.yml` extension for Airflow when ready.
