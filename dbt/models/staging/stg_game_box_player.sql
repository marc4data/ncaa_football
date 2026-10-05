-- Advanced box score, player grain: one row per (game, team, player). Usage, PPA and — since
-- A286 — advanced passing and rushing, side by side.
--
-- FOUR BLOCKS KEYED BY PLAYER NAME, joined the same way and for the same reason as the team
-- blocks: `players.usage`, `players.ppa`, `players.passing` and `players.rushing` are separate
-- arrays with no positional guarantee.
--
-- ⚠️ THE ATHLETE ID SITUATION CHANGED ON 2026-09-24 AND THIS COMMENT USED TO SAY THERE WAS
-- NONE (A286, cfdb-main-R-4890). `usage` and `ppa` still carry only a NAME, which is why the
-- grain is still (game, team, player_name) — two same-named players in one game would collide
-- there and nothing in those blocks could separate them. ✅ BUT THE NEW `passing` AND `rushing`
-- BLOCKS CARRY A REAL `playerId`, surfaced here as `player_id`. It is NULL for a player who
-- appears only in usage/ppa, so it is an additional key for the rows that have it rather than a
-- replacement for the grain. /games/players and /stats/player/season still carry ids for every
-- player and are the better join when you need one unconditionally.
--
-- 🚨 FOUR NEW SECTIONS ARRIVED BETWEEN CFBD v5.27.1 AND v5.32.1 AND TWO OF THEM ARE HERE.
-- A284 found that we had been landing `players.passing` and `players.rushing` since
-- 2026-09-24 12:03 UTC and unnesting neither. Measured at that point: 205 of 2,239 games
-- carry them (the rest were fetched before CFBD served them), 613 passing elements and 2,109
-- rushing elements at latest-per-game.
--
-- 🚨 THE SPINE HAD TO GROW, AND THIS IS THE ONE CHANGE THAT WOULD HAVE LOST DATA SILENTLY.
-- 280 of the 2,190 (game, player, team) keys in the new blocks DO NOT APPEAR in usage or ppa
-- — a rusher with carries but no charted usage row. The spine was a union over usage and ppa
-- only, so those 280 rows would have been dropped while every test passed and the row count
-- looked plausible. Measured before the change, not discovered after it.
--
-- ⚠️ `locations` (passing) AND `directions` (rushing) ARE DELIBERATELY NOT HERE. They are
-- maps, not scalars: 7 passing zones x 23 fields = 161 columns and 4 rushing directions x 15
-- = 60. Those are the grains (game, player, zone) and (game, player, direction), and pivoting
-- them onto a (game, player) row would be a 221-column widening of the wrong thing. Their own
-- models are cfdb-main-R-4891.
--
-- ⚠️ SEASON, WEEK, SEASON_TYPE, CONFERENCE AND OPPONENT ARE ON THE PAYLOAD AND NOT COLUMNED.
-- Every one is already owned upstream — `stg_games` has the schedule and `game_id` joins to
-- it — and a second copy is R-574's defect, which this file's own havoc comment is about. The
-- facts are queryable; they are just queryable in one place.
--
-- 🚨 TWELVE OF THE NEW FIELDS ARE COVERAGE COUNTERS, NOT STATISTICS. Anything ending
-- `...Available` or `...Eligible` — `air_yards_attempts_available`, `location_eligible_attempts`
-- and the rest — counts HOW MANY ATTEMPTS THE STATISTIC COULD BE COMPUTED FROM. Averaging one
-- is meaningless and summing one across games answers nothing about football. They are kept
-- because they are the denominator that tells you whether the paired measure is trustworthy
-- for a given game, which is exactly what a null-looking 0.0 cannot tell you.
--
-- ⚠️ EVERY NEW COLUMN USES `safe_numeric`, INCLUDING THE INTEGER-TYPED ONES, WHICH DEPARTS
-- FROM `cast(... as int)` ABOVE ON PURPOSE. 146 new columns land across this model and
-- stg_game_box_team on live Sunday data; `cast('1.5' as int)` RAISES in Postgres, and a single
-- unexpected decimal in a field the spec calls an integer would fail `dbt_run` and gate the
-- publish (§2.3). `safe_numeric` yields NULL instead of stopping the pipeline.
--
-- USAGE IS A SHARE AND PPA IS A RATE. `usage_total` of 0.042 means 4.2% of the team's plays;
-- `ppa_average_total` of -0.578 is points per play. Both are small decimals and neither is
-- the other.

{% set usage_splits = ['total', 'quarter1', 'quarter2', 'quarter3', 'quarter4',
                       'rushing', 'passing'] %}

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
    select game_id, {{ json_get_object('payload', 'players') }} as players
    from responses where recency = 1
),

{#- DEDUPED BEFORE THE JOIN, for the same reason as stg_game_box_team.
    CFBD emits the same TEAM twice inside a block in four games, which multiplied that model
    to 128 rows for one key. The exposure here is identical in shape — two blocks keyed by
    player name, joined — so a repeated player would double every row for that player.
    Cheaper to prevent than to detect: the grain sweep would catch it, but only after a
    build. #}
{% set player_blocks = ['usage', 'ppa', 'passing', 'rushing'] %}

{%- for block in player_blocks %}
{{ block }} as (
    select game_id, b
    from (
        select
            game_id,
            b,
            row_number() over (
                partition by game_id,
                             {{ json_get_string('b', 'player') }},
                             {{ json_get_string('b', 'team') }}
            ) as copy
        from (
            select game_id, {{ json_array_elements(json_get_object('players', block)) }} as b
            from latest
        ) exploded
    ) ranked
    where copy = 1
),
{% endfor %}

{#- 🚨 ALL FOUR BLOCKS, NOT JUST usage AND ppa. 280 of the new blocks' 2,190 keys appear in
    NEITHER usage NOR ppa, so a two-block union drops them silently. See the header. #}
spine as (
{%- for block in player_blocks %}
    {%- if not loop.first %}
    union
    {%- endif %}
    select game_id,
           {{ json_get_string('b', 'player') }} as player_name,
           {{ json_get_string('b', 'team') }}   as team
    from {{ block }}
{%- endfor %}
)

select
    s.game_id,
    s.player_name,
    s.team,
    coalesce({{ json_get_string('u.b', 'position') }},
             {{ json_get_string('p.b', 'position') }}) as position,
    -- Only the two NEW blocks carry an id; NULL for a usage/ppa-only player. See the header.
    coalesce({{ json_get_string('pa.b', 'playerId') }},
             {{ json_get_string('ru.b', 'playerId') }}) as player_id

{%- for split in usage_splits %},
    {{ safe_numeric(json_get_string('u.b', split)) }} as usage_{{ snake_case(split) }}
{%- endfor %}

{%- for block, prefix in [('average', 'ppa_average'), ('cumulative', 'ppa_cumulative')] %}
    {%- for split in usage_splits %},
    {{ safe_numeric(json_get_nested_string('p.b', [block, split])) }}
        as {{ prefix }}_{{ snake_case(split) }}
    {%- endfor %}
{%- endfor %}


{#- A286. EXHAUSTIVE BY CONSTRUCTION: these lists are the spec's own scalar property names for
    `PlayerPassingGame` and `PlayerRushingGame`, minus the identity fields and the two nested
    maps named in the header. Generated from config/api-docs.json rather than typed, because
    "every field the payload carries" is the policy and a hand-copied list is how one goes
    missing. #}
{% set passing_fields = [
    'airYardsAttemptsAvailable', 'attempts', 'completions', 'incompletions', 'interceptions',
    'locationAvailableAttempts', 'locationEligibleAttempts', 'ppaAttemptsAvailable',
    'successAttemptsAvailable', 'successfulAttempts', 'successfulPpaAttemptsAvailable',
    'totalAirYards', 'totalYards', 'totalYardsAfterCatch', 'totalYardsAttemptsAvailable',
    'yardsAfterCatchAttemptsAvailable', 'averageDepthOfTarget', 'averageYardsAfterCatch',
    'completionRate', 'explosiveness', 'ppa', 'successRate', 'totalPpa'
] %}
{% set rushing_fields = [
    'attempts', 'directionAvailableAttempts', 'directionEligibleAttempts',
    'individualAttempts', 'kneels', 'multiCarrierAttempts', 'rushingYardsAvailable', 'sacks',
    'teamRushes', 'totalRushingYards', 'unattributedAttempts', 'explosiveness', 'lineYards',
    'lineYardsTotal', 'openFieldYards', 'openFieldYardsTotal', 'powerSuccess', 'ppa',
    'secondLevelYards', 'secondLevelYardsTotal', 'stuffRate', 'successRate', 'totalPpa',
    'yardsPerCarry'
] %}
{%- for f in passing_fields %},
    {{ safe_numeric(json_get_string('pa.b', f)) }} as passing_{{ snake_case(f) }}
{%- endfor %}
{%- for f in rushing_fields %},
    {{ safe_numeric(json_get_string('ru.b', f)) }} as rushing_{{ snake_case(f) }}
{%- endfor %}

from spine s
left join usage u
    on u.game_id = s.game_id
   and {{ json_get_string('u.b', 'player') }} = s.player_name
   and {{ json_get_string('u.b', 'team') }} = s.team
left join ppa p
    on p.game_id = s.game_id
   and {{ json_get_string('p.b', 'player') }} = s.player_name
   and {{ json_get_string('p.b', 'team') }} = s.team
left join passing pa
    on pa.game_id = s.game_id
   and {{ json_get_string('pa.b', 'player') }} = s.player_name
   and {{ json_get_string('pa.b', 'team') }} = s.team
left join rushing ru
    on ru.game_id = s.game_id
   and {{ json_get_string('ru.b', 'player') }} = s.player_name
   and {{ json_get_string('ru.b', 'team') }} = s.team
