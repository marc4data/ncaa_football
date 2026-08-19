{{ config(materialized='table', tags=['ops', 'postgres_only']) }}
-- One row per dbt test per invocation. Transaction grain: each run is an observation, and
-- history is what makes the table worth having — the current state is already on screen in
-- the task log, but "how long has this been failing" is not.
--
-- Every test carries a severity of its own in dbt; what this adds is the *shape* of a
-- failure over time. A test that fails once is a blip, a test that has failed for six runs
-- is a broken pipeline nobody has looked at, and those need to be distinguishable.
with results as (
    select
        invocation_id,
        unique_id,
        test_name,
        generated_at,
        dbt_version,
        status,
        coalesce(failures, 0) as failures,
        execution_time,
        message,
        relation_name
    from {{ ref('stg_dbt_test_result') }}
)
select
    {{ surrogate_key(['invocation_id', 'unique_id']) }} as dq_test_result_sk,
    invocation_id,
    unique_id,
    test_name,
    generated_at,
    dbt_version,
    status,
    status in ('pass', 'success') as is_passing,
    failures,
    execution_time,
    message,
    relation_name,
    -- Which model the test guards, recovered from the relation dbt tested. Null for source
    -- tests, which guard a landed table rather than a model.
    case when relation_name is not null
         then {{ split_at("replace(relation_name, '\"', '')", '.', 2) }}
    end as tested_relation,
    row_number() over (partition by unique_id order by generated_at desc) as recency_rank
from results
