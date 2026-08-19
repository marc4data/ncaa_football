{{ config(tags=['postgres_only']) }}
-- Postgres-only. This model's source is cfdb's own telemetry, written directly to Postgres
-- by src/*.py rather than landed as a CFBD response, so it has no Databricks equivalent and
-- the analytics build excludes it by tag. Operational history belongs where the operations
-- are; the analytics warehouse has no use for dbt test outcomes.
-- dbt's own test outcomes, one row per test per invocation.
--
-- The unique_id encodes more than an identifier: `test.cfdb_dbt.<name>.<hash>` where the
-- name carries the test type and the model it guards. Splitting it is what lets the System
-- Overview page group failures by model without a second lookup table.
select
    invocation_id,
    unique_id,
    generated_at,
    dbt_version,
    status,
    failures,
    execution_time,
    message,
    relation_name,
    -- The hash suffix is a dbt implementation detail and changes when a test's config
    -- changes, so it is dropped: a test that keeps its name should keep its identity.
    {{ split_at('unique_id', '.', 3) }} as test_name
from {{ source('raw', 'raw_dbt_test_result') }}
