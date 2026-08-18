-- Consumption against every metered external resource cfdb depends on.
--
-- Grain: one row per (resource, observed_at).
--
-- Two resources, deliberately in one fact rather than two. They are different in every
-- detail — one counts calls against a published limit, the other counts seconds against an
-- unpublished one — but the question asked of them is identical and is asked at the same
-- moment: *are we about to lose a dependency?* Splitting them means answering it twice and
-- eventually answering it only once.
--
-- The two failure modes are worth stating, because they are not symmetrical:
--
--   cfbd_api             75,000 calls/month, published and observable. Exceeding it is a
--                        known quantity, and `/info` reports the position exactly.
--   databricks_warehouse No published threshold, and no API to read consumption back.
--                        Exceeding it shuts compute down "for the rest of the day (and in
--                        extreme cases, the rest of the month)". `limit_value` is null
--                        here and that null is the point: it means unknowable, not zero,
--                        and `pct_used` is null with it rather than guessing.
--
-- Only the site's dependencies could be user-visible, and neither of these is: the site
-- reads serving Postgres, so exhausting either costs freshness, never availability.
{{ config(materialized='table') }}

with cfbd as (
    select
        'cfbd_api'                    as resource,
        observed_at,
        'calls'                       as unit,
        used_calls                    as used_value,
        monthly_limit                 as limit_value,
        remaining_calls               as remaining_value,
        resets_at,
        tier_name                     as detail
    from {{ ref('stg_api_quota') }}
),

-- Databricks reports nothing, so consumption is accumulated from our own measurements.
-- A running total rather than per-operation seconds: the quota is consumed cumulatively,
-- so the comparable number to CFBD's `used_calls` is the sum to date, not the last run.
warehouse as (
    select
        'databricks_warehouse' as resource,
        observed_at,
        'seconds'              as unit,
        sum(elapsed_seconds) over (order by observed_at
                                   rows between unbounded preceding and current row)
                               as used_value,
        cast(null as numeric)  as limit_value,
        cast(null as numeric)  as remaining_value,
        cast(null as {{ type_timestamp_tz() }}) as resets_at,
        operation              as detail
    from {{ ref('stg_warehouse_usage') }}
)

select
    {{ surrogate_key(['resource', 'observed_at']) }} as api_usage_sk,
    resource,
    observed_at,
    unit,
    cast(used_value as numeric)      as used_value,
    cast(limit_value as numeric)     as limit_value,
    cast(remaining_value as numeric) as remaining_value,
    -- Null when the limit is unknown. A percentage of an unpublished threshold would be an
    -- invented number, and this table exists precisely to avoid guessing about quota.
    case
        when limit_value is null or limit_value = 0 then null
        else round(100.0 * used_value / limit_value, 2)
    end as pct_used,
    resets_at,
    detail
from (
    select * from cfbd
    union all
    select * from warehouse
) combined
