{{ config(materialized='table', tags=['production']) }}

-- One row per endpoint: how fresh its data is, and whether the last pull returned anything.
--
-- This is what "data as of X" on every site page reads from (data quality rule #5). It is
-- deliberately about the *pipeline*, not the football: a page can show a freshness stamp
-- and a warning without any page-specific plumbing.

with successful as (

    select *
    from {{ ref('stg_raw_manifest') }}
    where is_success

),

latest as (

    select endpoint, last_success_at, last_row_count, hours_since_fetch
    from (
        select
            endpoint,
            fetched_at as last_success_at,
            row_count  as last_row_count,
            hours_since_fetch,
            row_number() over (partition by endpoint order by fetched_at desc) as recency
        from successful
    ) ranked
    where recency = 1

),

totals as (

    select
        endpoint,
        count(*)                                                  as total_responses,
        count(case when is_success then 1 end)                    as successful_responses,
        count(case when not is_success then 1 end)                as failed_responses,
        count(case when is_success and is_empty then 1 end)       as empty_responses,
        max(row_count)                             as max_row_count
    from {{ ref('stg_raw_manifest') }}
    group by endpoint

),

-- Data loss has to be judged per *request*, not per endpoint. `records` returned 668 rows
-- for 2024 and 2025 and 0 for 2026 — that is a season that hasn't happened, not a
-- regression. Comparing an endpoint's newest response against its best response across
-- all params flags every endpoint the moment a new season opens.
latest_per_request as (

    select endpoint, params, latest_row_count
    from (
        select
            endpoint,
            params,
            row_count as latest_row_count,
            row_number() over (partition by endpoint, params order by fetched_at desc) as recency
        from successful
    ) ranked
    where recency = 1

),

best_per_request as (

    select endpoint, params, max(row_count) as best_row_count
    from successful
    group by endpoint, params

),

losses as (

    select
        l.endpoint,
        count(case
            when l.latest_row_count = 0 and b.best_row_count > 0 then 1
        end) as requests_that_lost_data
    from latest_per_request l
    join best_per_request b
        on b.endpoint = l.endpoint
       -- Null-safe equality without `is not distinct from`, which Spark spells `<=>`.
       and (b.params = l.params or (b.params is null and l.params is null))
    group by l.endpoint

)

select
    t.endpoint,
    l.last_success_at,
    round(cast(l.hours_since_fetch as numeric), 1) as hours_since_last_success,
    l.last_row_count,
    t.total_responses,
    t.successful_responses,
    t.failed_responses,
    t.empty_responses,
    t.max_row_count,
    -- An endpoint that has *never* returned rows is not a problem: plenty are legitimately
    -- empty before a season starts. A *request* that used to return rows and now returns
    -- none is the signal worth surfacing. Coalesced because an endpoint whose every
    -- response failed (coaches/tenures answers 400 without a coachId) has no latest
    -- success to judge, and null would read as "unknown" where the answer is "no".
    coalesce(x.requests_that_lost_data, 0) > 0 as lost_its_data,
    coalesce(x.requests_that_lost_data, 0)     as requests_that_lost_data,
    l.last_success_at is null                  as never_succeeded
from totals t
left join latest l on l.endpoint = t.endpoint
left join losses x on x.endpoint = t.endpoint
