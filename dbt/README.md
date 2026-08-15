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

Prerequisites: `docker compose up -d postgres`, then land and load data — see the repo
README's "Full rebuild from scratch".

## Models

| Model | Grain | Notes |
|---|---|---|
| `stg_teams` | team × season | Season-scoped: fed only by year-parameterized `/teams` fetches |
| `stg_games` | game | Deduped per distinct request params, so regular + postseason both survive |
| `mart_team_season_record` | team × season | W-L-T, scoring, `is_listed_team` |

## Conventions

- **Staging filters failed fetches.** Raw lands 401s and 500s too; `status_code = 200`
  is enforced in staging so nulls never reach a mart.
- **Staging deduplicates fetches.** Every pull writes a new raw file, so staging keeps the
  latest file **per distinct request params** — not per season. The backfill fetches each
  season twice (`seasonType=regular` and `postseason`), so deduping on season alone would
  silently discard the bowl games. Re-running ingestion must not multiply rows, and must
  not drop any either — data quality rule #2.
- **Season-scoped dimensions.** `/teams` answers differently per year: Boise State was
  Mountain West in 2024 and Pac-12 today. `stg_teams` is fed only by year-parameterized
  fetches, and marts join on `(season, team_id)`.
- **Marts flag rather than drop.** Schedules include lower-division opponents absent from
  CFBD's season team list. Those team-seasons stay in the mart with `is_listed_team = false`,
  because dropping them would break the invariant that every game yields one win and one loss.
- **Marts declare their grain** via a `*_key` column with a `unique` test on it.
