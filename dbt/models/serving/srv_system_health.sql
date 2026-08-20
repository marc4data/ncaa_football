{{ config(tags=['postgres_only']) }}
-- Postgres-only. This model's source is cfdb's own telemetry, written directly to Postgres
-- by src/*.py rather than landed as a CFBD response, so it has no Databricks equivalent and
-- the analytics build excludes it by tag. Operational history belongs where the operations
-- are; the analytics warehouse has no use for dbt test outcomes.
-- System Overview page: one row per health signal, unioned across four sources.
--
-- A union rather than four views because the page asks one question — is anything wrong —
-- and answering it from four tables would put the judgement in the app. `severity` is
-- assigned here so the page sorts by it without knowing what any of the signals mean.
--
-- Airflow run history is deliberately absent: nothing outside Airflow should read Airflow's
-- metadata database, and task outcomes are already visible in its own UI and in the failure
-- alerts. This page is about data, not about the scheduler.
with freshness as (
    select
        'freshness'                                        as signal_type,
        endpoint                                           as subject,
        case when lost_its_data then 'error'
             when hours_since_last_success > 168 then 'warn'
             else 'ok' end                                 as severity,
        case when lost_its_data
             then 'Endpoint used to return rows and its latest response is empty'
             else 'Last loaded ' || cast(round(hours_since_last_success) as {{ dbt.type_string() }})
                  || ' hours ago' end                      as detail,
        last_success_at                                    as observed_at
    from {{ ref('mart_data_freshness') }}
),
tests as (
    select
        'data_quality'                                     as signal_type,
        test_name                                          as subject,
        case when is_passing then 'ok' else 'error' end    as severity,
        case when is_passing then 'Passing'
             else cast(failures as {{ dbt.type_string() }}) || ' failing row(s)' end as detail,
        generated_at                                       as observed_at
    from {{ ref('fct_dq_test_result') }}
    -- Latest invocation only. History is what the fact is for; the page is a status board.
    where recency_rank = 1
),
quota as (
    select
        'quota'                                            as signal_type,
        resource                                           as subject,
        case when pct_used is null then 'unknown'
             when pct_used > 90 then 'error'
             when pct_used > 70 then 'warn'
             else 'ok' end                                 as severity,
        case when pct_used is null
             -- Databricks publishes no threshold, so "unknown" is the honest severity and
             -- the detail says why rather than implying the number is missing by accident.
             then 'No published limit; ' || cast(used_value as {{ dbt.type_string() }})
                  || ' ' || unit || ' consumed'
             else cast(pct_used as {{ dbt.type_string() }}) || '% of '
                  || cast(limit_value as {{ dbt.type_string() }}) || ' ' || unit end as detail,
        observed_at
    from {{ ref('fct_api_usage') }}
    where observed_at = (select max(observed_at) from {{ ref('fct_api_usage') }} f2
                         where f2.resource = {{ ref('fct_api_usage') }}.resource)
),
documentation as (
    select
        'documentation'                                    as signal_type,
        layer                                              as subject,
        case when min(case when is_documented then 1 else 0 end) = 1 then 'ok'
             else 'warn' end                               as severity,
        cast(sum(case when is_documented then 1 else 0 end) as {{ dbt.type_string() }}) || ' of '
            || cast(count(*) as {{ dbt.type_string() }}) || ' columns documented' as detail,
        cast(null as {{ type_timestamp_tz() }})            as observed_at
    from {{ ref('dim_field_metadata') }}
    group by layer
),

-- Deploy drift. Added after production spent a day building a dbt project with 39 models
-- while development had 56 — no error and no alert, because a pinned tree that requires a
-- person to advance it is a tree that will be stale again. Latest observation only; the
-- history is in the staging model.
deployment as (
    select
        'deployment'                                       as signal_type,
        'airflow deploy tree'                              as subject,
        severity,
        detail,
        observed_at
    from {{ ref('fct_deploy_status') }}
    where recency_rank = 1
)

select
    {{ surrogate_key(['signal_type', 'subject']) }} as system_health_sk,
    signal_type, subject, severity, detail, observed_at,
    ao_src.as_of_ts
from (
    select * from freshness
    union all select * from tests
    union all select * from quota
    union all select * from documentation
    union all select * from deployment
) combined
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'ops') ao_src
