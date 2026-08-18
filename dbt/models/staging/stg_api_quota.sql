-- One row per `/info` snapshot: where CFBD call consumption stood at that moment.
--
-- Unlike every other staging model, this keeps *every* landed response rather than the
-- latest per params. That is the whole point: `/info` reports a running total that resets
-- monthly, so a single snapshot answers "how many calls have we used" and only a series
-- answers "are we heading for the limit". The params are always empty, so a
-- latest-per-params rule would collapse the history to one row.
with responses as (
    select
        r.filename,
        m.fetched_at as observed_at,
        {{ json_get_object('r.content', 'data') }} as payload
    from {{ source('raw', 'raw_info') }} r
    join {{ source('raw', 'raw_manifest') }} m
        on m.endpoint = 'info' and m.filename = r.filename
    where r.status_code = 200
)
select
    filename,
    observed_at,
    {{ json_get_string('payload', 'tierName') }}                          as tier_name,
    cast({{ json_get_string('payload', 'patronLevel') }} as int)          as patron_level,
    cast({{ json_get_string('payload', 'monthlyLimit') }} as bigint)      as monthly_limit,
    cast({{ json_get_string('payload', 'usedCalls') }} as bigint)         as used_calls,
    cast({{ json_get_string('payload', 'remainingCalls') }} as bigint)    as remaining_calls,
    cast({{ json_get_string('payload', 'resetAt') }} as {{ type_timestamp_tz() }}) as resets_at,
    -- The pool is shared across CFB and CBB, which matters when reading `used_calls`:
    -- a request made by a different project against the same key spends this budget too.
    cast({{ json_get_string('payload', 'sharedPool') }} as boolean)       as is_shared_pool
from responses
