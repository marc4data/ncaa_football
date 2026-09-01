-- Advanced box score, team grain: one row per (game, team). The widest model in the project.
--
-- EIGHT BLOCKS, EACH A TWO-ELEMENT ARRAY KEYED BY TEAM NAME. `teams.ppa`, `cumulativePpa`,
-- `successRates`, `explosiveness`, `rushing`, `havoc`, `scoringOpportunities` and
-- `fieldPosition` each hold one entry per side, and nothing but the team string ties them
-- together.
--
-- THE BLOCKS DO NOT AGREE ON ORDER, AND NOT OCCASIONALLY. Measured across the landed games:
-- `havoc` lists the opposite team from `ppa` in 104 of 104 — every single one — while
-- `rushing` matches `ppa` in all of them. A positional read would therefore attach every
-- game's havoc numbers to the wrong team, silently and universally, while looking correct
-- for the blocks that happen to line up.
--
-- So each block is unnested independently and joined on (game_id, team). The join is by name
-- because the name is the only thing the API guarantees.
--
-- QUARTER SPLITS EVERYWHERE. ppa, cumulativePpa, successRates and explosiveness each carry
-- total plus quarter1-4, so the metric names alone would collide four ways; the quarter is
-- part of the column name. `quarter3` and `quarter4` are NULL in a game that ended early or
-- was not fully charted, and null is kept — a quarter with no plays is not a quarter with
-- zero PPA.
--
-- CUMULATIVE AND PER-PLAY ARE BOTH HERE AND ARE DIFFERENT SCALES. `ppa_overall_total` is per
-- play (1.34); `cumulative_ppa_overall_total` is the game total (28.2). Same statistic, and
-- plotting them on one axis is meaningless.
--
-- Game id comes from `params`, as in stg_game_box_info — the payload never names its game.

{% set quarters = ['total', 'quarter1', 'quarter2', 'quarter3', 'quarter4'] %}
{% set ppa_groups = ['overall', 'passing', 'rushing'] %}
{% set rate_groups = ['overall', 'standardDowns', 'passingDowns'] %}

with responses as (

    select
        filename,
        cast({{ json_get_string('params', 'id') }} as bigint) as game_id,
        {{ json_get_object('content', 'data') }}              as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'id') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_game_box_advanced') }}
    where status_code = 200
      and {{ json_get_string('params', 'id') }} is not null

),

latest as (
    select game_id, {{ json_get_object('payload', 'teams') }} as teams
    from responses where recency = 1
),

{#- One CTE per block. Verbose, and the alternative is a positional read that is wrong on the
    games where CFBD orders a block differently — a failure that would affect two teams at a
    time and look like a data quality problem in the source. #}
ppa as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'ppa')) }} as b from latest
),
cumulative_ppa as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'cumulativePpa')) }} as b from latest
),
success_rates as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'successRates')) }} as b from latest
),
explosiveness as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'explosiveness')) }} as b from latest
),
rushing as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'rushing')) }} as b from latest
),
havoc as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'havoc')) }} as b from latest
),
scoring_opportunities as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'scoringOpportunities')) }} as b from latest
),
field_position as (
    select game_id, {{ json_array_elements(json_get_object('teams', 'fieldPosition')) }} as b from latest
),

-- The spine: every (game, team) that appears in ANY block. A block missing for one team must
-- not drop that team's row, so this is a union rather than a base table plus joins.
spine as (
    select game_id, {{ json_get_string('b', 'team') }} as team from ppa
    union
    select game_id, {{ json_get_string('b', 'team') }} from cumulative_ppa
    union
    select game_id, {{ json_get_string('b', 'team') }} from success_rates
    union
    select game_id, {{ json_get_string('b', 'team') }} from rushing
)

select
    s.game_id,
    s.team,

    cast({{ json_get_string('p.b', 'plays') }} as int) as plays
{%- for group in ppa_groups %}
    {%- for q in quarters %},
    {{ safe_numeric(json_get_nested_string('p.b', [group, q])) }}
        as ppa_{{ snake_case(group) }}_{{ snake_case(q) }}
    {%- endfor %}
{%- endfor %}
{%- for group in ppa_groups %}
    {%- for q in quarters %},
    {{ safe_numeric(json_get_nested_string('c.b', [group, q])) }}
        as cumulative_ppa_{{ snake_case(group) }}_{{ snake_case(q) }}
    {%- endfor %}
{%- endfor %}
{%- for group in rate_groups %}
    {%- for q in quarters %},
    {{ safe_numeric(json_get_nested_string('sr.b', [group, q])) }}
        as success_rate_{{ snake_case(group) }}_{{ snake_case(q) }}
    {%- endfor %}
{%- endfor %}
{%- for q in quarters %},
    {{ safe_numeric(json_get_nested_string('e.b', ['overall', q])) }}
        as explosiveness_{{ snake_case(q) }}
{%- endfor %},

    {{ safe_numeric(json_get_string('r.b', 'powerSuccess')) }}            as power_success,
    {{ safe_numeric(json_get_string('r.b', 'stuffRate')) }}               as stuff_rate,
    {{ safe_numeric(json_get_string('r.b', 'lineYards')) }}               as line_yards,
    {{ safe_numeric(json_get_string('r.b', 'lineYardsAverage')) }}        as line_yards_average,
    {{ safe_numeric(json_get_string('r.b', 'secondLevelYards')) }}        as second_level_yards,
    {{ safe_numeric(json_get_string('r.b', 'secondLevelYardsAverage')) }} as second_level_yards_average,
    {{ safe_numeric(json_get_string('r.b', 'openFieldYards')) }}          as open_field_yards,
    {{ safe_numeric(json_get_string('r.b', 'openFieldYardsAverage')) }}   as open_field_yards_average,

    -- Whether a team's havoc row describes havoc its defence CAUSED or havoc its offence
    -- SUFFERED is not stated by the API and is not asserted here — the endpoint gives a team
    -- and a number. What is established is that this block is ordered opposite to `ppa` in
    -- every landed game, which is why it is joined by name; the semantic direction needs a
    -- reconciliation against stg_game_team_havoc before anything downstream relies on it.
    {{ safe_numeric(json_get_string('h.b', 'total')) }}      as havoc_total,
    {{ safe_numeric(json_get_string('h.b', 'frontSeven')) }} as havoc_front_seven,
    {{ safe_numeric(json_get_string('h.b', 'db')) }}         as havoc_db,

    cast({{ json_get_string('so.b', 'opportunities') }} as int)         as scoring_opportunities,
    cast({{ json_get_string('so.b', 'points') }} as int)                as scoring_opportunity_points,
    {{ safe_numeric(json_get_string('so.b', 'pointsPerOpportunity')) }} as points_per_opportunity,

    {{ safe_numeric(json_get_string('fp.b', 'averageStart')) }} as average_start,
    {{ safe_numeric(json_get_string('fp.b', 'averageStartingPredictedPoints')) }}
                                                                as average_starting_predicted_points

from spine s
left join ppa p
    on p.game_id = s.game_id and {{ json_get_string('p.b', 'team') }} = s.team
left join cumulative_ppa c
    on c.game_id = s.game_id and {{ json_get_string('c.b', 'team') }} = s.team
left join success_rates sr
    on sr.game_id = s.game_id and {{ json_get_string('sr.b', 'team') }} = s.team
left join explosiveness e
    on e.game_id = s.game_id and {{ json_get_string('e.b', 'team') }} = s.team
left join rushing r
    on r.game_id = s.game_id and {{ json_get_string('r.b', 'team') }} = s.team
left join havoc h
    on h.game_id = s.game_id and {{ json_get_string('h.b', 'team') }} = s.team
left join scoring_opportunities so
    on so.game_id = s.game_id and {{ json_get_string('so.b', 'team') }} = s.team
left join field_position fp
    on fp.game_id = s.game_id and {{ json_get_string('fp.b', 'team') }} = s.team
