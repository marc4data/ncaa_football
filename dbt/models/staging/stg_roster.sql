-- Team rosters: one row per (season, player, TEAM). 22,843 players for 2024.
--
-- TEAM IS IN THE GRAIN BECAUSE A PLAYER CAN BE ON TWO ROSTERS IN ONE SEASON. Ten of them in
-- 2024 — Ahmari Huggins-Bruce appears for both Louisville and South Carolina, Micah Davis
-- for Ole Miss and Utah State — where a mid-season move leaves the player listed by both
-- schools. Same id, same name, two rows, and both are true.
--
-- Keying on (season, player_id) would look right on any sample that happened to miss those
-- ten and would silently drop one row per transfer. Found by the grain sweep against real
-- data; the fixture now carries the case.
--
-- SEASON COMES FROM THE REQUEST, NOT THE ROW — and this is the trap on this endpoint. There
-- IS a `year` field on every player, but it is their CLASS YEAR (1 = freshman, 4 = senior),
-- not the season. Reading `year` as the season would put every senior in 4 AD. The season is
-- only in `params`, so unparameterized fetches are excluded exactly as stg_teams excludes
-- them, and the class year is named `class_year` so the two cannot be confused.
--
-- `recruitIds` IS AN ARRAY, carried as JSON. It is the bridge from a rostered player back to
-- stg_recruit — the link that endpoint's own `athleteId` provides in the other direction,
-- and which is null there for anyone unlinked. Between the two, most players can be joined
-- to their recruiting record; neither alone is enough.
--
-- Hometown carries coordinates and a county FIPS code, spelled `homeCountyFIPS` here against
-- `fipsCode` on /recruiting/players and `countyFips` on /draft/picks. Three endpoints, one
-- concept, three spellings; the column name is aligned so callers do not have to know.

with season_fetches as (

    select
        filename,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_roster') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

players as (

    select season, {{ json_array_elements('payload') }} as player
    from season_fetches
    where recency = 1

)

select
    season,
    {{ json_get_string('player', 'id') }}                     as player_id,
    {{ json_get_string('player', 'firstName') }}              as first_name,
    {{ json_get_string('player', 'lastName') }}               as last_name,
    {{ json_get_string('player', 'team') }}                   as team,
    {{ json_get_string('player', 'position') }}               as position,
    cast({{ json_get_string('player', 'jersey') }} as int)    as jersey,
    -- CLASS year (1-4), NOT the season. See the header.
    cast({{ json_get_string('player', 'year') }} as int)      as class_year,
    cast({{ json_get_string('player', 'height') }} as int)    as height_inches,
    cast({{ json_get_string('player', 'weight') }} as int)    as weight_pounds,
    {{ json_get_string('player', 'homeCity') }}               as home_city,
    {{ json_get_string('player', 'homeState') }}              as home_state,
    {{ json_get_string('player', 'homeCountry') }}            as home_country,
    {{ safe_numeric(json_get_string('player', 'homeLatitude')) }}  as home_latitude,
    {{ safe_numeric(json_get_string('player', 'homeLongitude')) }} as home_longitude,
    {{ json_get_string('player', 'homeCountyFIPS') }}         as home_fips_code,
    -- JSON array. The bridge back to stg_recruit; see the header.
    {{ json_get_object('player', 'recruitIds') }}             as recruit_ids
from players
