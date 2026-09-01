-- One row per `/info/usage` snapshot per endpoint: which endpoints spent the calls.
--
-- The quota total says whether we are close to the limit; this says what to change if we
-- are. Every cadence decision in the project — 4-hourly lines, daily Databricks, whether a
-- mid-week results run is affordable — is really a question about this table.
--
-- `topEndpoints` is truncated by the API's `limit` parameter, so this is the top N per
-- snapshot and not the full set. `total_requests` from the same response is the honest
-- denominator; summing this model's rows is not.
with responses as (
    select
        r.filename,
        m.fetched_at as observed_at,
        {{ json_get_object('r.content', 'data') }} as payload
    from {{ source('raw', 'raw_info_usage') }} r
    join {{ source('raw', 'raw_manifest') }} m
        -- `info_usage`, not `info/usage`: `src/ingest.fetch` flattens the slash so the
        -- endpoint can be a directory name, and the manifest records the flattened form.
        -- Joining on the API path silently returns zero rows — no error, just an empty
        -- model, which is why the CI fixture now carries this endpoint.
        on m.endpoint = 'info_usage' and m.filename = r.filename
    where r.status_code = 200
),
flattened as (
    select
        filename,
        observed_at,
        cast({{ json_get_nested_string('payload', ['totals', 'requests']) }} as bigint)
            as total_requests,
        {{ json_get_nested_string('payload', ['window', 'start']) }} as window_start_raw,
        {{ json_get_nested_string('payload', ['window', 'end']) }}   as window_end_raw,
        -- THE TOTALS BLOCK, EXTRACTED HERE BECAUSE `payload` IS ONLY IN SCOPE IN THIS CTE.
        -- These are window-level figures on an endpoint-grain model, so they denormalise
        -- across the rows — deliberately, because the alternative is a second model whose
        -- only content is three numbers.
        --
        -- `cfbRequests` and `cbbRequests` are the split behind the shared pool that
        -- stg_api_quota.is_shared_pool warns about: `total_requests` includes both, so a CFB
        -- budget read from the total alone counts basketball calls as football ones.
        cast({{ json_get_nested_string('payload', ['totals', 'cfbRequests']) }} as bigint)
            as cfb_requests,
        cast({{ json_get_nested_string('payload', ['totals', 'cbbRequests']) }} as bigint)
            as cbb_requests,
        cast({{ json_get_nested_string('payload', ['totals', 'uniqueEndpoints']) }} as int)
            as unique_endpoints,
        {{ json_array_elements(json_get_object('payload', 'topEndpoints')) }} as endpoint_row
    from responses
)
select
    filename,
    observed_at,
    cast(window_start_raw as {{ type_timestamp_tz() }}) as window_start,
    cast(window_end_raw as {{ type_timestamp_tz() }})   as window_end,
    total_requests,
    {{ json_get_string('endpoint_row', 'endpoint') }}   as endpoint,
    {{ json_get_string('endpoint_row', 'api') }}        as api,
    cast({{ json_get_string('endpoint_row', 'requests') }} as bigint) as requests,
    cast({{ json_get_string('endpoint_row', 'lastUsedAt') }} as {{ type_timestamp_tz() }})
        as last_used_at,
    cfb_requests,
    cbb_requests,
    unique_endpoints
from flattened
