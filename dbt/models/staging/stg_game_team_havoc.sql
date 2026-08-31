-- Havoc rates: one row per (game, team), offense and defense side by side.
--
-- Havoc is the share of plays ending in a tackle for loss, pass defensed, forced fumble or
-- interception, split by front seven and defensive backs. /stats/game/havoc publishes it
-- from both perspectives on the same row — `offense` is havoc INFLICTED ON this team's
-- offense, `defense` is havoc this team's defense created. Both are kept and neither is
-- renamed, because renaming them to "allowed" and "created" would be an interpretation, and
-- staging's job is to represent the endpoint.
--
-- This endpoint also carries both conferences, which stg_game_team_advanced does not.

{% set havoc_metrics = [
    'totalPlays', 'totalHavocEvents', 'frontSevenHavocEvents', 'dbHavocEvents',
    'havocRate', 'frontSevenHavocRate', 'dbHavocRate',
] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_game_havoc') }}
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
    {{ json_get_string('row_json', 'opponent') }}               as opponent,
    {{ json_get_string('row_json', 'opponentConference') }}     as opponent_conference

{%- for side in ['offense', 'defense'] %}
    {%- for metric in havoc_metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
