-- Advanced season profile: one row per (season, team), offense and defense side by side.
--
-- /stats/season/advanced is the widest payload CFBD serves — 82 field paths — and the
-- season-level companion to stg_game_team_advanced. Same structure, plus four things the
-- per-game version does not carry: a `rate` on each down/play split, field position, havoc,
-- and scoring opportunities.
--
-- Same wide-and-generated construction as the per-game model, for the same reason: the
-- schema is fixed and typed, and generating both sides from one list makes a
-- `defense_x reads offense.x` mix-up unrepresentable rather than merely unlikely.
--
-- `totalOpportunies` IS SPELLED THAT WAY ON THE WIRE. It is CFBD's typo, not ours, and it is
-- the actual JSON key — reading `totalOpportunities` returns null for every row, silently.
-- The wire key is preserved in the lookup and the column is named correctly, which is the
-- only combination that is both truthful and usable.

{% set flat_metrics = [
    'plays', 'drives', 'ppa', 'totalPPA', 'successRate', 'explosiveness',
    'powerSuccess', 'stuffRate',
    'lineYards', 'lineYardsTotal',
    'secondLevelYards', 'secondLevelYardsTotal',
    'openFieldYards', 'openFieldYardsTotal',
    'pointsPerOpportunity',
] %}

{% set grouped_metrics = {
    'standardDowns': ['rate', 'ppa', 'successRate', 'explosiveness'],
    'passingDowns':  ['rate', 'ppa', 'successRate', 'explosiveness', 'totalPPA'],
    'rushingPlays':  ['rate', 'ppa', 'totalPPA', 'successRate', 'explosiveness'],
    'passingPlays':  ['rate', 'ppa', 'totalPPA', 'successRate', 'explosiveness'],
    'fieldPosition': ['averageStart', 'averagePredictedPoints'],
    'havoc':         ['total', 'frontSeven', 'db'],
} %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_season_advanced') }}
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

{%- for side in ['offense', 'defense'] %}
    {%- for metric in flat_metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %},
    {#- CFBD's spelling, deliberately. See the header. #}
    {{ safe_numeric(json_get_nested_string('row_json', [side, 'totalOpportunies'])) }}
        as {{ side }}_total_opportunities
    {%- for group, metrics in grouped_metrics.items() %}
    {%- for metric in metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, group, metric])) }}
        as {{ side }}_{{ snake_case(group) }}_{{ snake_case(metric) }}
    {%- endfor %}
    {%- endfor %}
{%- endfor %}

from deduped
