-- Passer production for a season: one row per (season, player).
--
-- New in spec v5.25.0 and 2025 onward — 2022, 2023 and 2024 all answer 200 with an EMPTY
-- ARRAY, which is why src/endpoints.py floors this at min_season 2025 and why seasons_for
-- now enforces that floor in every path.
--
-- RICHER THAN THE BOX SCORE, NOT A DUPLICATE OF IT. stg_game_player_stat has completions and
-- yards; this has air yards, depth of target and yards after catch — the throw itself rather
-- than its result.
--
-- THE AVAILABILITY COUNTS ARE THE POINT OF READING THIS CAREFULLY. See macros/passing.sql:
-- `average_depth_of_target` is computed over `air_yards_attempts_available` passes, not over
-- `attempts`, and the two differ by a factor of three in the landed data.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_passing_players_season') }}
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
                    {{ json_get_string('row_json', 'playerId') }}
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
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference

{%- for metric in passing_metrics() %},
    {{ safe_numeric(json_get_string('row_json', metric)) }} as {{ snake_case(metric) }}
{%- endfor %}

from deduped
