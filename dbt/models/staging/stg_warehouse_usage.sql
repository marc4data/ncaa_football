{{ config(tags=['postgres_only']) }}
-- Postgres-only. This model's source is cfdb's own telemetry, written directly to Postgres
-- by src/*.py rather than landed as a CFBD response, so it has no Databricks equivalent and
-- the analytics build excludes it by tag. Operational history belongs where the operations
-- are; the analytics warehouse has no use for dbt test outcomes.
-- One row per measured Databricks operation.
--
-- Not a CFBD endpoint: this is cfdb's own telemetry, landed by `src/warehouse_usage.py`
-- because Databricks Free Edition publishes "no access to the account console or
-- account-level APIs" and so cannot be asked what it has spent. Client-side elapsed
-- wall-clock is the only measurement available, and it over-states compute because it
-- includes the cold start.
select
    observed_at,
    operation,
    outcome,
    cast(elapsed_seconds as numeric) as elapsed_seconds,
    catalog
from {{ source('raw', 'raw_warehouse_usage') }}
