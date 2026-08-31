-- Player success rate for a single game: one row per (game, player).
--
-- The per-game companion to stg_player_season_success, same passing/rushing split plus the
-- game, week and opponent.
--
-- A THIRD OF THE LANDED FETCHES ARE 400s, and that is correct rather than a fault. CFBD
-- rejects a year-only call here — "week required when team and playerId not specified" — so
-- the early season-scoped attempts were refused and the registry now fetches this per week.
-- The failed responses are kept in raw because the raw layer is immutable; `status_code = 200`
-- is what excludes them, and it is the reason this model must never be written to read the
-- payload before checking the status.

{% set success_metrics = ['plays', 'successes', 'successRate'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_player_success_game') }}
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
                    {{ json_get_string('row_json', 'gameId') }},
                    {{ json_get_string('row_json', 'id') }}
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
    {{ json_get_string('row_json', 'id') }}                     as player_id,
    {{ json_get_string('row_json', 'name') }}                   as player_name,
    {{ json_get_string('row_json', 'position') }}               as position,
    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'conference') }}             as conference,
    {{ json_get_string('row_json', 'opponent') }}               as opponent

{%- for side in ['passing', 'rushing'] %}
    {%- for metric in success_metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
