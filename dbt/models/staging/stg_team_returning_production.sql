-- Returning production: one row per (season, team).
--
-- TEAM GRAIN DESPITE THE ENDPOINT NAME. /player/returning sits under the player namespace but
-- publishes nothing about individual players — it is the share of last season's production
-- coming back, aggregated per team. Naming this model stg_player_* would put it next to the
-- player-grain models and invite a join that cannot work.
--
-- THREE SCALES, ONE ROW. `total*PPA` are absolute PPA totals; `percent*PPA` are the SHARE of
-- the prior season returning, 0 to 1; `*usage` are share-of-snaps, also 0 to 1. A chart that
-- put totalPPA and percentPPA on one axis would be comparing 100.6 with 0.338.

{% set totals = ['totalPPA', 'totalPassingPPA', 'totalReceivingPPA', 'totalRushingPPA'] %}
{% set percents = ['percentPPA', 'percentPassingPPA', 'percentReceivingPPA',
                   'percentRushingPPA'] %}
{% set usage = ['usage', 'passingUsage', 'receivingUsage', 'rushingUsage'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_player_returning') }}
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
                    {{ json_get_string('row_json', 'team') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference

{%- for metric in totals + percents + usage %},
    {{ safe_numeric(json_get_string('row_json', metric)) }} as {{ snake_case(metric) }}
{%- endfor %}

from deduped
