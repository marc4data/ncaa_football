-- Team passing for a single game: one row per (game, team), offense and defense side by side.
--
-- The per-game companion to stg_passing_team_season. Two rows per game, one per team, so a
-- game and its opponent are both present and joinable on game_id.
--
-- `defense_*` is passing ALLOWED, as in the season model — lower is better on those columns.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_passing_teams_games') }}
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
                    {{ json_get_string('row_json', 'team') }}
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
    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'conference') }}             as conference,
    {{ json_get_string('row_json', 'opponent') }}               as opponent

{%- for side in ['offense', 'defense'] %}
    {%- for metric in passing_metrics() %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
