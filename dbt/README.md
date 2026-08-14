# dbt — cfdb transforms

Raw CFBD responses → staging → marts. Phase 1 targets the local Compose Postgres;
a Databricks target gets added once the model shape is settled.

## Layout

| Path | What |
|---|---|
| `models/staging/` | One row per entity, unpacked from the raw JSON. Views. |
| `models/marts/` | Business grain, materialized as tables. Feeds the site. |
| `tests/` | Singular reconciliation tests (rule #4). Generic tests live in the `_models.yml` files. |

## Running it

The repo's `profiles.yml.example` is the template. Because a `~/.dbt/profiles.yml`
may already exist for other projects, the local convention is a repo-local profile:

```bash
cp dbt/profiles.yml.example dbt/profiles.yml   # gitignored
cd dbt
DBT_PROFILES_DIR=. dbt debug
DBT_PROFILES_DIR=. dbt run
DBT_PROFILES_DIR=. dbt test
```

Prerequisites: `docker compose up -d postgres`, then load raw data:

```bash
python -m src.ingest fetch teams
python -m src.ingest fetch games --year 2024 --seasonType regular
python -m src.load_raw_to_postgres teams
python -m src.load_raw_to_postgres games
```

## Conventions

- **Staging filters failed fetches.** Raw lands 401s and 500s too; `status_code = 200`
  is enforced in staging so nulls never reach a mart.
- **Staging deduplicates fetches.** Every pull writes a new raw file, so staging takes
  the latest file (per season, for season-scoped endpoints). Re-running ingestion must
  not multiply rows — data quality rule #2.
- **Marts declare their grain** via a `*_key` column with a `unique` test on it.
