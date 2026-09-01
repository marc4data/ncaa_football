-- One row per recruit per class: individual recruiting rankings from /recruiting/players.
--
-- TWO IDS, AND THEY ARE NOT THE SAME THING. `id` is the RECRUIT record; `athleteId` is the
-- player once they exist as a college athlete, and it is null for recruits who never
-- enrolled or have not yet been linked. Joining player stats on `id` returns nothing;
-- joining on `athleteId` silently drops every unlinked recruit. Both are carried, named for
-- what they are.
--
-- `committedTo` IS NULL FOR UNCOMMITTED RECRUITS — data, not a gap, exactly as
-- stg_player_portal.destination_team is.
--
-- `height` IS INCHES and `weight` is pounds; neither carries a unit on the wire.
--
-- hometownInfo is coordinates plus a FIPS county code, which is what makes recruiting
-- geography mappable at all.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_recruiting_players') }}
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
                partition by {{ json_get_string('row_json', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('row_json', 'id') }}                     as recruit_id,
    -- Null until the recruit exists as a college athlete. See the header.
    {{ json_get_string('row_json', 'athleteId') }}              as athlete_id,
    cast({{ json_get_string('row_json', 'year') }} as int)      as recruiting_class,
    {{ json_get_string('row_json', 'recruitType') }}            as recruit_type,
    cast({{ json_get_string('row_json', 'ranking') }} as int)   as national_ranking,
    {{ json_get_string('row_json', 'name') }}                   as name,
    {{ json_get_string('row_json', 'school') }}                 as high_school,
    {{ json_get_string('row_json', 'committedTo') }}            as committed_to,
    {{ json_get_string('row_json', 'position') }}               as position,
    -- NUMERIC, NOT INT, BECAUSE THIS ENDPOINT REPORTS HALF-INCHES.
    --
    -- /recruiting/players lists heights like 74.5 — a recruit measured at 6 feet 2 and a
    -- half. 1,021 rows carry one. `cast(... as int)` does not round them, it RAISES, so this
    -- view could not be read at all: any query touching the column failed with "invalid
    -- input syntax for type integer: 79.5".
    --
    -- It hid for months because Postgres prunes unreferenced columns out of a view's target
    -- list. count(*), the uniqueness sweep and the not-silently-empty sweep never selected
    -- this column, so they never evaluated the cast and all passed. The first thing to ask
    -- for every column was the staging export, which is how it surfaced.
    --
    -- Note /roster reports WHOLE inches and stg_roster's int cast there is correct. Two
    -- endpoints, two conventions, and assuming one from the other is what produced this.
    {{ safe_numeric(json_get_string('row_json', 'height')) }}   as height_inches,
    cast({{ json_get_string('row_json', 'weight') }} as int)    as weight_pounds,
    cast({{ json_get_string('row_json', 'stars') }} as int)     as stars,
    {{ safe_numeric(json_get_string('row_json', 'rating')) }}   as rating,
    {{ json_get_string('row_json', 'city') }}                   as city,
    {{ json_get_string('row_json', 'stateProvince') }}          as state_province,
    {{ json_get_string('row_json', 'country') }}                as country,
    {{ safe_numeric(json_get_nested_string('row_json', ['hometownInfo', 'latitude'])) }}
        as hometown_latitude,
    {{ safe_numeric(json_get_nested_string('row_json', ['hometownInfo', 'longitude'])) }}
        as hometown_longitude,
    {{ json_get_nested_string('row_json', ['hometownInfo', 'fipsCode']) }}
        as hometown_fips_code
from deduped
