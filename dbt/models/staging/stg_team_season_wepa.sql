-- Opponent-adjusted (wEPA) team profile: one row per (season, team).
--
-- CFBD's adjusted metrics — EPA, success rate, rushing yardage splits and explosiveness,
-- each published TWICE: once for what the team did, once for what it allowed. The `_allowed`
-- half is the defensive side, and the endpoint expresses it as a suffixed sibling object
-- rather than a `defense` block, which is why this model loops over ['', 'Allowed'] where
-- the ppa and advanced-stats models loop over ['offense', 'defense'].
--
-- THE ONE METRICS ENDPOINT THAT SHIPS A TEAM ID. /ratings/*, /ppa/* and /stats/season/advanced
-- all identify a team by name only, and every model over them says so and defers resolution
-- to a mart. This one carries `teamId`, so it joins to dim_team directly — the single place
-- in the adjusted-metrics family where a name-keyed join is not forced on the caller.
--
-- `epa` AND `epaAllowed` ARE BOTH "HIGHER IS MORE EPA". Neither is inverted: a team with
-- high `epa_allowed_total` has a bad defence. Same convention as the ppa models, and for the
-- same reason — flipping the sign would silently disagree with the API's own numbers.

{% set blocks = {
    'epa':         ['total', 'passing', 'rushing'],
    'successRate': ['total', 'standardDowns', 'passingDowns'],
    'rushing':     ['lineYards', 'secondLevelYards', 'openFieldYards', 'highlightYards'],
} %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_wepa_team_season') }}
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
                    {{ json_get_string('row_json', 'year') }},
                    {{ json_get_string('row_json', 'teamId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)   as season,
    cast({{ json_get_string('row_json', 'teamId') }} as int) as team_id,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference

{%- for block, metrics in blocks.items() %}
{%- for side in ['', 'Allowed'] %}
    {%- for metric in metrics %},
    {{ safe_numeric(json_get_nested_string('row_json', [block ~ side, metric])) }}
        as {{ snake_case(block ~ side) }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}
{%- endfor %},

    -- Scalars rather than blocks; the same `_allowed` pairing one level up.
    {{ safe_numeric(json_get_string('row_json', 'explosiveness')) }}        as explosiveness,
    {{ safe_numeric(json_get_string('row_json', 'explosivenessAllowed')) }} as explosiveness_allowed
from deduped
