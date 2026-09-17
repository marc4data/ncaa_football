{{ config(tags=['postgres_only']) }}
-- Postgres-only. This model's source is cfdb's own telemetry, written directly to Postgres by
-- src/heartbeat.py rather than landed as a CFBD response, so it has no Databricks equivalent
-- and the analytics build excludes it by tag. Operational history belongs where the operations
-- are; the analytics warehouse has no use for pipeline heartbeats.
-- One row per cadence per successful run: the DAG's final `beat` task writes it.
--
-- 🚨 WHAT MAKES THIS TABLE MEAN SOMETHING IS ITS POSITION IN THE DAG, NOT ITS CONTENTS.
-- Both `weekly_refresh_dag.py` and `scores_refresh_dag.py` end
--     fetch >> load >> dbt_run >> dbt_catalogue >> dbt_test >> publish >> beat
-- so **the beat is downstream of the publish** and cannot advance while the publish is failing.
-- A stale beat is therefore a stopped publish, which is precisely what nobody was told on
-- 2026-09-16 (A156 §7): the alert could not leave the host and twenty hours passed.
--
-- ⚠️ THE CHARTER'S §2.3 SAYS "heartbeat is not downstream of dbt_test, so the DAG kept beating
-- throughout". That was true of the wiring on 2026-09-11 and is not true of the code above.
-- **Read the DAG, not the rule** — and the rule should be corrected.
select
    heartbeat_name,
    beat_at
from {{ source('ops', 'pipeline_heartbeat') }}
