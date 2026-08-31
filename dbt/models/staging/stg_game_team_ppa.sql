-- Team PPA for a single game: one row per (game, team).
--
-- The per-game companion to stg_team_season_ppa: the same six offensive and six defensive
-- splits, no cumulative block — a single game has no season total to accumulate.
--
-- Carries `opponent`, which the season model cannot. Two rows exist per game, one per team,
-- so a game's own row and its opponent's are both present and joinable on game_id.

{% set splits = ['overall', 'passing', 'rushing', 'firstDown', 'secondDown', 'thirdDown'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ppa_games') }}
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
    {%- for metric in splits %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
