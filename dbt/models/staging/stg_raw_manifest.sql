-- One row per landed API response, across every endpoint.
--
-- The spine for two things the pipeline could not otherwise answer:
--   "how old is this data?"        -> fetched_at, the observation time, not the load time
--   "did we get anything back?"    -> row_count, captured at load
--
-- Unlike the other staging models this one does not deduplicate. Every fetch is a fact
-- about the pipeline, including the ones that were superseded a minute later.

select
    endpoint,
    filename,
    params,
    status_code,
    status_code between 200 and 299 as is_success,
    row_count,
    row_count = 0                   as is_empty,
    fetched_at,
    loaded_at,
    -- Staleness is measured against observation, not load: reloading old files must not
    -- make stale data look fresh.
    {{ hours_between('now()', 'fetched_at') }} as hours_since_fetch
from {{ source('raw', 'raw_manifest') }}
