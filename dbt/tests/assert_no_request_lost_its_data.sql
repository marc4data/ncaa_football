-- The silent failure this project is most exposed to: CFBD answers 200 with an empty
-- array, the DAG goes green, and nobody notices until a page is blank.
--
-- Rather than guess a row-count threshold per endpoint — which would need a season to
-- calibrate and would be wrong for the preseason — this compares each request against
-- *itself*. For an identical (endpoint, params), if an earlier fetch returned rows and the
-- most recent one returned none, something broke. Legitimately-empty endpoints never trip
-- it, because they never had rows to lose.

with successful as (

    select endpoint, params, row_count, fetched_at
    from {{ ref('stg_raw_manifest') }}
    where is_success

),

latest_per_request as (

    select distinct on (endpoint, params)
        endpoint,
        params,
        row_count as latest_row_count,
        fetched_at as latest_fetched_at
    from successful
    order by endpoint, params, fetched_at desc

),

best_per_request as (

    select endpoint, params, max(row_count) as best_row_count
    from successful
    group by endpoint, params

)

select
    l.endpoint,
    l.params,
    l.latest_fetched_at,
    l.latest_row_count,
    b.best_row_count
from latest_per_request l
join best_per_request b
    on b.endpoint = l.endpoint
   and b.params is not distinct from l.params
where l.latest_row_count = 0
  and b.best_row_count > 0
