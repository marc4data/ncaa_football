{{ config(materialized='table') }}

-- ONE TEAM'S CONTRIBUTION TO ONE MEASURE, IN ONE GAME. Long: one row per (game, team, metric).
-- R-808.
--
-- 🚨 A TABLE, AND IT IS A TABLE FOR THE REASON THE BUILD TAUGHT ME RATHER THAN THE ONE I
-- EXPECTED. The first version of `fct_game_team_metric_distribution` held this as a CTE and
-- referenced it twice — once for the percentiles, once for the whisker pass. Postgres
-- materialises a CTE referenced more than once, and the build failed:
--
--     could not resize shared memory segment "/PostgreSQL.3005280788" to 33554432 bytes:
--     No space left on device
--
-- That is A097's and A108's exact error, on a different model. Eighteen metrics over 225,350
-- team-games is roughly four million rows, and a parallel sort over that spills to /dev/shm.
--
-- ✅ AND THE PROJECT HAD ALREADY SOLVED THIS SHAPE: `int_week_metric_value` is a TABLE feeding
-- both the game-grain distribution and its bin counts, with "ONE DEFINITION, TWO CONSUMERS" in
-- its own header. This is that pattern at team grain. The rows are computed once, ANALYZEd, and
-- every downstream estimate is real.
--
-- ⚠️ THE POPULATION RULE IS READ, NOT REIMPLEMENTED. FBS only, spelled as
-- `fct_team_week_metric_distribution` spells it — `dim_team.classification = 'fbs'` — because a
-- distribution over a different population than the page's own numbers is a lie the reader
-- cannot see.
--
-- ⚠️ READS THE TWO MARTS, NOT `srv_game_team`. `ci/check_layering.py` refused that on the
-- sibling model and the correction is recorded there: "a mart reaching up into serving is the
-- same bypass as a serving view reaching down past marts". `srv_game_team` joins these two on
-- `game_team_sk`; this is that join, one layer down.
{% set metrics = var('game_team_distribution_metrics') %}

-- 🚨 ONE SCAN, UNPIVOTED WITH `LATERAL`, AND THE FIRST VERSION'S EIGHTEEN `union all` BRANCHES
-- ARE WHY. Each branch re-scanned the same two-mart join, so eighteen metrics meant eighteen
-- passes over 225,350 team-games — and the parallel plan for that exhausted shared memory:
--
--     could not resize shared memory segment ... No space left on device
--
-- the same error A097 and A108 both hit, on different models. A `lateral (values ...)` reads the
-- join ONCE and emits eighteen rows per team-game from the row already in hand. It is also the
-- honest shape: the eighteen measures are columns of one row, not eighteen separate facts.
select
    t.season, t.season_type, t.week, t.game_id, t.team_id,
    v.metric,
    v.value
from {{ ref('fct_game_team') }} t
join {{ ref('fct_game_team_advanced') }} a
  on a.game_team_sk = t.game_team_sk
join {{ ref('dim_team') }} d
  on d.season = t.season and d.team_id = t.team_id
cross join lateral (values
    {% for metric in metrics %}
    (cast('{{ metric }}' as {{ dbt.type_string() }}),
     cast({{ metric }} as {{ dbt.type_numeric() }})){{ "," if not loop.last }}
    {% endfor %}
) as v(metric, value)
where d.classification = 'fbs'
