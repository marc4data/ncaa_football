-- Transfer portal entries: one row per (season, player, origin).
--
-- NO PLAYER ID ON THIS ENDPOINT — the only identifier is a first and last name, and the
-- portal is precisely where a player's team changes, so name is the least stable key
-- available at the moment it matters most. The grain therefore includes `origin`: the same
-- name entering from two different schools is two entries, and collapsing them on name alone
-- would silently merge two people.
--
-- `destination` IS NULL FOR A LARGE SHARE OF ROWS and that is meaningful data, not missing
-- data: it means entered the portal, not yet committed. Anything counting transfers into a
-- school must filter it out; anything counting entries must not.
--
-- `rating` is null far more often than `stars`. Both are recruiting-service measures carried
-- verbatim; a null rating with 4 stars is a real combination, not an inconsistency.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_player_portal') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'season') }},
                    {{ json_get_string('row_json', 'firstName') }},
                    {{ json_get_string('row_json', 'lastName') }},
                    {{ json_get_string('row_json', 'origin') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'firstName') }}           as first_name,
    {{ json_get_string('row_json', 'lastName') }}            as last_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'origin') }}              as origin_team,
    -- Null means "in the portal, not yet committed". See the header.
    {{ json_get_string('row_json', 'destination') }}         as destination_team,
    cast({{ json_get_string('row_json', 'transferDate') }} as {{ type_timestamp_tz() }})
                                                             as transfer_at,
    {{ safe_numeric(json_get_string('row_json', 'rating')) }} as rating,
    cast({{ json_get_string('row_json', 'stars') }} as int)   as stars,
    {{ json_get_string('row_json', 'eligibility') }}          as eligibility
from deduped
