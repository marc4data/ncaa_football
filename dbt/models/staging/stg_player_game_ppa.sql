-- Player PPA for a single game: one row per (season, season type, week, player).
--
-- NO gameId ON THIS PAYLOAD, WHICH IS WHY THE GRAIN LOOKS ODD. Every other per-game endpoint
-- carries the id; this one identifies the game only by season, week, season type and
-- opponent. So the key is the player and the week, and joining to stg_games needs the
-- (season, week, season_type, team) tuple rather than an id — one more reason the team-name
-- resolution this project defers to marts eventually has to happen somewhere.
--
-- MUCH THINNER THAN THE SEASON MODEL, AND NOT BY OMISSION. /ppa/players/games publishes only
-- averagePPA, and only its `all` / `pass` / `rush` keys — no totalPPA object, no down splits.
-- Both are the endpoint's full content: eleven fields, all of them here.
--
-- NO CONFERENCE COLUMN, for the same reason. The payload has none.

{% set splits = ['all', 'pass', 'rush'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ppa_players_games') }}
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
                    {{ json_get_string('row_json', 'seasonType') }},
                    {{ json_get_string('row_json', 'week') }},
                    {{ json_get_string('row_json', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    cast({{ json_get_string('row_json', 'week') }} as int)   as week,
    {{ json_get_string('row_json', 'seasonType') }}          as season_type,
    {{ json_get_string('row_json', 'id') }}                  as player_id,
    {{ json_get_string('row_json', 'name') }}                as player_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'opponent') }}            as opponent

{%- for metric in splits %},
    {{ safe_numeric(json_get_nested_string('row_json', ['averagePPA', metric])) }}
        as average_ppa_{{ snake_case(metric) }}
{%- endfor %}

from deduped
