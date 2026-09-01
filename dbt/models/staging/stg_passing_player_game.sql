-- Passer production for a single game: one row per (game, player).
--
-- The per-game companion to stg_passing_player_season, same thirteen measures plus the game,
-- week and opponent. Carries a real gameId, so it joins to stg_games without a name match —
-- unlike /ppa/players/games, which identifies its game by week and opponent alone.
--
-- Same availability caveat as the season model; see macros/passing.sql.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_passing_players_games') }}
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
                    {{ json_get_string('row_json', 'gameId') }},
                    {{ json_get_string('row_json', 'playerId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'gameId') }} as bigint) as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)    as season,
    cast({{ json_get_string('row_json', 'week') }} as int)      as week,
    {{ json_get_string('row_json', 'seasonType') }}             as season_type,
    {{ json_get_string('row_json', 'playerId') }}               as player_id,
    {{ json_get_string('row_json', 'player') }}                 as player_name,
    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'conference') }}             as conference,
    {{ json_get_string('row_json', 'opponent') }}               as opponent

{%- for metric in passing_metrics() %},
    {{ safe_numeric(json_get_string('row_json', metric)) }} as {{ snake_case(metric) }}
{%- endfor %}

from deduped
