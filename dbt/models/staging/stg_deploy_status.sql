{{ config(tags=['postgres_only']) }}
-- Deploy-tree drift: how far Airflow's pinned worktree is behind main.
--
-- cfdb's own telemetry, Postgres-only. Not a CFBD endpoint and not something Databricks has
-- any use for — it describes the machine the pipeline runs on.
select
    observed_at,
    deploy_sha,
    main_sha,
    commits_behind,
    severity,
    detail
from {{ source('raw', 'raw_deploy_status') }}
