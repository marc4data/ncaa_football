-- Advanced box score: one row per (game, team), offense and defense side by side.
--
-- /stats/game/advanced publishes 62 field paths — the richest per-game payload CFBD serves —
-- and until now nothing read any of them. PPA, success rate, explosiveness, line yards,
-- stuff rate, and the same set again split by standard/passing downs and rushing/passing
-- plays. This is the analytical substance of the API, and it was landing into a table with
-- no model on it.
--
-- WIDE, NOT LONG, unlike the box-score models next door. The distinction is whether the key
-- set is open. /games/teams and /games/players ship category names CFBD can add to at will,
-- so enumerating them is a decision to drop the next one silently, and those models land
-- long. The advanced schema is FIXED and typed in the spec: the columns are known, the
-- values are numbers, and a wide table is what makes them usable — `select team,
-- offense_ppa, defense_ppa` rather than a pivot every caller has to write.
--
-- OFFENSE AND DEFENSE ARE GENERATED FROM ONE LIST, and that is the load-bearing decision
-- here. The two objects have identical inner shapes, so the hand-written version is a
-- hundred and twenty near-identical lines. The failure that invites is not a typo — a typo
-- does not compile. It is `defense_ppa` reading `offense.ppa`: compiles, runs, passes every
-- null and range check, and is wrong in a way nothing downstream can detect. Deriving both
-- sides from one list makes that error unrepresentable rather than unlikely.

{% set flat_metrics = [
    'plays', 'drives', 'ppa', 'totalPPA', 'successRate', 'explosiveness',
    'powerSuccess', 'stuffRate',
    'lineYards', 'lineYardsTotal',
    'secondLevelYards', 'secondLevelYardsTotal',
    'openFieldYards', 'openFieldYardsTotal',
] %}

{% set grouped_metrics = {
    'standardDowns': ['ppa', 'successRate', 'explosiveness'],
    'passingDowns':  ['ppa', 'successRate', 'explosiveness'],
    'rushingPlays':  ['ppa', 'totalPPA', 'successRate', 'explosiveness'],
    'passingPlays':  ['ppa', 'totalPPA', 'successRate', 'explosiveness'],
} %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_stats_game_advanced') }}
    where status_code = 200

),

exploded as (

    select
        filename,
        {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

-- Dedup on the entity, not on `params`. /stats/game/advanced is fetched per (year,
-- seasonType), and a week-scoped fetch beside a season-scoped one would return the same
-- games under different params — the failure that put 211 duplicate game_ids into fct_game
-- and 111 duplicate rows into stg_game_media. Partitioning on the grain itself is immune to
-- how the request happened to be shaped.
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
    -- Team and opponent by NAME; this endpoint ships no ids. Resolution needs a
    -- season-scoped team map and belongs in a mart, not here.
    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'opponent') }}               as opponent

{%- for side in ['offense', 'defense'] %}
    {#- The whole point: one list, both sides, no opportunity to cross the wires. #}
    {%- for metric in flat_metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
    {%- for group, metrics in grouped_metrics.items() %}
    {%- for metric in metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, group, metric])) }}
        as {{ side }}_{{ snake_case(group) }}_{{ snake_case(metric) }}
    {%- endfor %}
    {%- endfor %}
{%- endfor %}

from deduped
