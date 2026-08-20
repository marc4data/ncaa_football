{{ config(materialized='table', tags=['ops', 'postgres_only']) }}
-- One row per deploy-drift observation.
--
-- Exists because serving builds on marts, never on staging — the CI layering guard caught
-- srv_system_health reading stg_deploy_status directly, which is the rule doing its job.
-- The model is thin on purpose: the interesting logic is in src/deploy_status.py, and a
-- passthrough that satisfies the layer boundary is better than a boundary with an exception
-- carved in it.
select
    {{ surrogate_key(['observed_at']) }} as deploy_status_sk,
    observed_at,
    deploy_sha,
    main_sha,
    commits_behind,
    severity,
    detail,
    row_number() over (order by observed_at desc) as recency_rank
from {{ ref('stg_deploy_status') }}
