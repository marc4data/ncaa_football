-- Opponent-adjusted rushing value per player: one row per (season, athlete).
--
-- Flat and small — wEPA plus the play count it was earned over. The play count matters:
-- wEPA is a per-play average, so a 0.48 over 304 plays and a 0.48 over 12 are not the same
-- claim, and any leaderboard built on this needs a minimum-plays filter that only `plays`
-- can express.
--
-- ITS OWN MODEL RATHER THAN A UNION WITH THE OTHER wepa PLAYER ENDPOINTS. Passing, rushing
-- and kicking are three separate endpoints with three separate raw tables, and kicking does
-- not even use the same metric name. Merging them would make the coverage matrix report on
-- a model rather than on the endpoints, which is the one thing it must not do.
--
-- `athleteId` is a string in the spec and stays one, matching every other player model here.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_wepa_players_rushing') }}
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
                    {{ json_get_string('row_json', 'year') }},
                    {{ json_get_string('row_json', 'athleteId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)  as season,
    {{ json_get_string('row_json', 'athleteId') }}          as athlete_id,
    {{ json_get_string('row_json', 'athleteName') }}        as athlete_name,
    {{ json_get_string('row_json', 'position') }}           as position,
    {{ json_get_string('row_json', 'team') }}               as team,
    {{ json_get_string('row_json', 'conference') }}         as conference,
    {{ safe_numeric(json_get_string('row_json', 'wepa')) }} as wepa,
    cast({{ json_get_string('row_json', 'plays') }} as int) as plays
from deduped
