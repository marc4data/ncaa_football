-- Advanced box score, team grain: one row per (game, team). The widest model in the project.
--
-- TEN BLOCKS, EACH A TWO-ELEMENT ARRAY KEYED BY TEAM NAME. `teams.ppa`, `cumulativePpa`,
-- `successRates`, `explosiveness`, `rushing`, `havoc`, `scoringOpportunities`,
-- `fieldPosition` and — since A286 — `passing` and `rushingAdvanced` each hold one entry per
-- side, and nothing but the team string ties them together.
--
-- 🚨 TWO BLOCKS ARRIVED BETWEEN CFBD v5.27.1 AND v5.32.1 AND WE DROPPED THEM FOR ELEVEN DAYS
-- (A286, cfdb-main-R-4890, from A284's R-4832). `teams.passing` and `teams.rushingAdvanced`
-- have landed on every fetch since 2026-09-24 12:03 UTC — 205 of 2,239 games, 410 elements
-- each at latest-per-game — and nothing unnested them.
--
-- 🚨 THESE TWO ARE SHAPED DIFFERENTLY FROM THE OTHER EIGHT AND THERE WAS NO PRECEDENT HERE.
-- The eight original blocks are FLAT: a team string and its metrics. The two new ones nest
-- `offense` and `defense`, each a full production object — 23 scalar fields for passing, 26
-- for rushing — so a side becomes part of the COLUMN NAME: `passing_offense_attempts`,
-- `rushing_advanced_defense_line_yards`. ⚠️ The prompt for this round said several existing
-- sections already had that shape; they do not, and the convention being followed is the
-- JOIN-BY-NAME one, not an offense/defense one that did not exist.
--
-- ⚠️ THE PREFIX IS `rushing_advanced_`, NOT `rushing_`, AND THAT IS NOT DECORATION. The OLD
-- `rushing` block already gives this model bare `line_yards`, `second_level_yards`,
-- `open_field_yards`, `power_success` and `stuff_rate`. `rushingAdvanced` carries every one of
-- those names again, per side. Un-prefixed they would collide with the existing columns, and
-- the collision would be silent in a `select` that happened to pick one.
--
-- ✅ AND THE OFFENSE/DEFENSE ASSIGNMENT IS RECONCILED RATHER THAN TRUSTED, which is this
-- file's own havoc lesson applied before shipping instead of after. Measured across all 410
-- landed (game, team) pairs: a team's `passing_offense_attempts` EQUALS its opponent's
-- `passing_defense_attempts` in 410 of 410, with zero nulls on either side.
-- `assert_a_teams_passing_offense_is_its_opponents_passing_defense` holds that invariant.
--
-- 🚨 AND WHAT THAT ASSERTION CANNOT SEE IS WRITTEN DOWN, BECAUSE A286 STAGED THE BREAK AND IT
-- CAME BACK GREEN. Swapping `offense` and `defense` for BOTH teams leaves the invariant
-- satisfied — `a.offense == b.defense` and `a.defense == b.offense` are the same pair of
-- equations read in the other direction, so a UNIFORM swap maps the test onto itself. The
-- assertion catches an ASYMMETRIC error: a misjoin that attaches the wrong team, or one side
-- reading the wrong sub-object. Proven, not assumed — pointing `passing_defense_*` at the
-- offense object fails it on 398 of 410 pairs.
--
-- ⚠️ SO THE DIRECTION OF THESE TWO BLOCKS IS NOT FULLY PINNED, EXACTLY AS `havoc`'s IS NOT.
-- Catching a uniform swap needs an INDEPENDENT source of how many passes a team threw —
-- `stg_game_team_stat` from /games/teams — which is a cross-relation test with the refresh
-- boundary that implies. Raised as cfdb-main-R-4893 rather than half-built here.
--
-- ⚠️ THE SPINE IS DELIBERATELY NOT EXTENDED FOR THESE TWO, AND THAT IS A MEASUREMENT.
-- `stg_game_box_player` DID need its spine widened — 280 keys there appear only in the new
-- blocks. Here the answer is 0 of 410: every (game, team) in `passing`/`rushingAdvanced`
-- already appears in ppa, cumulativePpa, successRates or rushing. So a union change would add
-- no rows, and leaving the spine alone keeps this model's row count provably unmoved.
--
-- ⚠️ `locations` AND `directions` ARE NOT HERE. They are maps at a finer grain — 7 passing
-- zones and 4 rushing directions, each a production object — and flattening them per side
-- would add hundreds of columns at the wrong grain. Their own models are cfdb-main-R-4891.
--
-- 🚨 SOME NEW FIELDS ARE COVERAGE COUNTERS, NOT STATISTICS. Anything containing `Available`
-- or `Eligible` counts how many attempts the paired statistic could be computed from.
-- Averaging one is meaningless. They are kept because they are the denominator that says
-- whether a given game's measure is trustworthy.
--
-- THE BLOCKS DO NOT AGREE ON ORDER, AND NOT OCCASIONALLY. Measured across the landed games:
-- `havoc` lists the opposite team from `ppa` in 104 of 104 — every single one — while
-- `rushing` matches `ppa` in all of them. A positional read would therefore attach every
-- game's havoc numbers to the wrong team, silently and universally, while looking correct
-- for the blocks that happen to line up.
--
-- So each block is unnested independently and joined on (game_id, team). The join is by name
-- because the name is the only thing the API guarantees.--
-- CFBD SOMETIMES EMITS THE SAME TEAM TWICE INSIDE A BLOCK. Four games of 1,849 have a
-- three-element `ppa` array for a two-team game — Eastern Michigan once and Saint Francis
-- twice. The copies are byte-identical, so which survives does not matter, but joining the
-- blocks when each contains a duplicate MULTIPLIES — 2^7 = 128 rows for one (game, team) when
-- there were eight blocks, and 2^9 = 512 now that A286 has made it ten.
-- That is exactly what happened, and the grain sweep caught it on the first full build.
--
-- So each block is deduped to one row per (game, team) BEFORE the joins. Deduping after
-- would be too late — the explosion happens in the join.
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

{#- ONE CTE PER BLOCK, GENERATED AND DEDUPED.
    Generated because ten near-identical CTEs invite a copy-paste error, and deduped
    because CFBD sometimes emits the SAME TEAM TWICE inside a block. See the header. #}
{% set blocks = ['ppa', 'cumulativePpa', 'successRates', 'explosiveness',
                 'rushing', 'havoc', 'scoringOpportunities', 'fieldPosition',
                 'passing', 'rushingAdvanced'] %}

{%- for block in blocks %}
{{ snake_case(block) }} as (
    select game_id, b
    from (
        select
            game_id,
            b,
            row_number() over (partition by game_id, {{ json_get_string('b', 'team') }}) as copy
        from (
            select game_id, {{ json_array_elements(json_get_object('teams', block)) }} as b
            from latest
        ) exploded
    ) ranked
    where copy = 1
),
{% endfor %}

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

    -- Whether a team's havoc row describes havoc its defense CAUSED or havoc its offense
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


{#- A286. EXHAUSTIVE BY CONSTRUCTION: the spec's own scalar property names for
    `PassingProduction` and `TeamRushingProduction`, minus the nested maps. Each is emitted
    once per SIDE, so the side is in the column name. #}
{% set team_passing_fields = [
    'airYardsAttemptsAvailable', 'attempts', 'completions', 'incompletions', 'interceptions',
    'locationAvailableAttempts', 'locationEligibleAttempts', 'ppaAttemptsAvailable',
    'successAttemptsAvailable', 'successfulAttempts', 'successfulPpaAttemptsAvailable',
    'totalAirYards', 'totalYards', 'totalYardsAfterCatch', 'totalYardsAttemptsAvailable',
    'yardsAfterCatchAttemptsAvailable', 'averageDepthOfTarget', 'averageYardsAfterCatch',
    'completionRate', 'explosiveness', 'ppa', 'successRate', 'totalPpa'
] %}
{% set team_rushing_adv_fields = [
    'attempts', 'directionAvailableAttempts', 'directionEligibleAttempts',
    'individualAttempts', 'kneels', 'multiCarrierAttempts', 'rushingTouchdowns',
    'rushingYardsAvailable', 'sacks', 'teamRushes', 'totalRushingYards',
    'touchdownStatusAvailable', 'unattributedAttempts', 'explosiveness', 'lineYards',
    'lineYardsTotal', 'openFieldYards', 'openFieldYardsTotal', 'powerSuccess', 'ppa',
    'secondLevelYards', 'secondLevelYardsTotal', 'stuffRate', 'successRate', 'totalPpa',
    'yardsPerCarry'
] %}
{%- for side in ['offense', 'defense'] %}
    {%- for f in team_passing_fields %},
    {{ safe_numeric(json_get_nested_string('tp.b', [side, f])) }}
        as passing_{{ side }}_{{ snake_case(f) }}
    {%- endfor %}
{%- endfor %}
{%- for side in ['offense', 'defense'] %}
    {%- for f in team_rushing_adv_fields %},
    {{ safe_numeric(json_get_nested_string('tra.b', [side, f])) }}
        as rushing_advanced_{{ side }}_{{ snake_case(f) }}
    {%- endfor %}
{%- endfor %}

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
left join passing tp
    on tp.game_id = s.game_id and {{ json_get_string('tp.b', 'team') }} = s.team
left join rushing_advanced tra
    on tra.game_id = s.game_id and {{ json_get_string('tra.b', 'team') }} = s.team
