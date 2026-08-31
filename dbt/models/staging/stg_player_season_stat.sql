-- Player season totals, long: one row per (season, player, category, stat type).
--
-- /stats/player/season is flat and EAV-shaped — category "defensive", statType "PD",
-- stat "0" — and at 132,277 rows for a single 2024 fetch it is the highest-volume endpoint
-- in the stats family. Landed verbatim; values stay strings because statType is open-ended
-- and each type carries its own units.
--
-- This has a REAL PLAYER ID, unlike the game-level box scores. `playerId` is a string in the
-- spec and stays one — it looks numeric, and casting is a guess about an identifier CFBD
-- never promised is one.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_player_season') }}
    where status_code = 200

),

exploded as (

    select
        filename,
        {{ json_array_elements('payload') }} as row_json
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
                    {{ json_get_string('row_json', 'playerId') }},
                    {{ json_get_string('row_json', 'category') }},
                    {{ json_get_string('row_json', 'statType') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'playerId') }}            as player_id,
    {{ json_get_string('row_json', 'player') }}              as player_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference,
    {{ json_get_string('row_json', 'category') }}            as stat_category,
    {{ json_get_string('row_json', 'statType') }}            as stat_type,
    {{ json_get_string('row_json', 'stat') }}                as stat_raw
from deduped
