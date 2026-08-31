-- Player success rate for a season: one row per (season, player), passing and rushing
-- side by side.
--
-- Success rate is the share of plays that gained enough to stay on schedule. /stats/player/
-- success splits it into passing and rushing objects with identical shapes, so the two are
-- generated from one list for the same reason the advanced models are: a `rushing_plays`
-- that reads `passing.plays` compiles and passes every check.
--
-- `successRate` IS NULL WHEN plays IS ZERO, which is most rows — a receiver has no passing
-- plays. safe_numeric keeps those null rather than coercing to 0, because 0% success on no
-- attempts and 0% success on twenty attempts are not the same fact and averaging them
-- together is the mistake this preserves the ability to avoid.

{% set success_metrics = ['plays', 'successes', 'successRate'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_player_success') }}
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
                    {{ json_get_string('row_json', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'id') }}                  as player_id,
    {{ json_get_string('row_json', 'name') }}                as player_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference

{%- for side in ['passing', 'rushing'] %}
    {%- for metric in success_metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
