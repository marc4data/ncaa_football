-- The recent-request log from /info/usage: one row per (api, endpoint, requested_at).
--
-- A SECOND ARRAY ON THE SAME PAYLOAD, at a different grain from `topEndpoints`. That one is
-- an aggregate — how many calls each endpoint took in the window; this is the tail of
-- individual calls with their timestamps. stg_api_usage_endpoint models the first and had no
-- place for `requestedAt`, which is why this exists rather than another column there.
--
-- WHAT IT IS ACTUALLY FOR. The aggregate says an endpoint was called 400 times this window;
-- only this says WHEN, which is the difference between "the sweep ran" and "something is
-- calling /games every ninety seconds". It is the finest-grained evidence available for
-- diagnosing quota being consumed unexpectedly, and the only place the API exposes it.
--
-- The window is short — CFBD returns a tail, not a full history — so this is a rolling
-- snapshot rather than a log to accumulate.

with responses as (

    select
        r.filename,
        m.fetched_at as observed_at,
        {{ json_get_object('r.content', 'data') }} as payload
    from {{ source('raw', 'raw_info_usage') }} r
    join {{ source('raw', 'raw_manifest') }} m
        on m.endpoint = 'info_usage' and m.filename = r.filename
    where r.status_code = 200

),

exploded as (

    select
        filename,
        observed_at,
        {{ json_array_elements(json_get_object('payload', 'recentRequests')) }} as row_json
    from responses

),

deduped as (

    select filename, observed_at, row_json
    from (
        select
            filename,
            observed_at,
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'api') }},
                    {{ json_get_string('row_json', 'endpoint') }},
                    {{ json_get_string('row_json', 'requestedAt') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    filename,
    observed_at,
    {{ json_get_string('row_json', 'api') }}      as api,
    {{ json_get_string('row_json', 'endpoint') }} as endpoint,
    cast({{ json_get_string('row_json', 'requestedAt') }} as {{ type_timestamp_tz() }})
                                                  as requested_at
from deduped
