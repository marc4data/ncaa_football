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
-- 🚨 THE POPULATION IS GATED ON THE GAME, NOT ON THE TEAM — A142, cfdb-main-R-962. IT USED TO
-- READ `join dim_team d ... where d.classification = 'fbs'`, one row at a time, and that rule is
-- ASYMMETRIC BY CONSTRUCTION: an FBS team's yards against an FCS opponent enter the pool and the
-- opponent's matching figure never does, because the opponent is not in the population.
--
-- Marc, 2026-09-16, having spotted it from the picture: *"If Oregon gained 497 yards last week.
-- the opponent would have Allowed 497 and the match for setting the min/max and quartiles would
-- lead to the same results."* ✅ HE IS RIGHT, AND AT THIS GRAIN IT IS AN EXACT IDENTITY RATHER
-- THAN AN APPROXIMATION — see the invariant note below.
--
-- 📊 WHAT THE OLD RULE COST, MEASURED ON 2026 regular `total_yards` at game grain:
--
--     population                        n     p25     p50      p75    mean
--     team is FBS (the old rule)      285   319.0   398.0    502.0  409.52   <- gained
--     team is FBS (the old rule)      285   223.0   322.0    413.0  326.40   <- allowed
--     the game involves an FBS side   370   255.5   367.0   474.75  367.51   <- gained
--     the game involves an FBS side   370   255.5   367.0   474.75  367.51   <- allowed
--
-- 🚨 A SEVENTY-SIX YARD GAP AT THE MEDIAN BETWEEN TWO NUMBERS THAT DESCRIBE THE SAME GAMES, and
-- exactly zero once the pool is closed. 85 of 285 FBS team-games this season — 29.8% — had no
-- mirror in the old pool. In a finished season (2025) it is 126 of 1,650, 7.6%: ⚠️ THE
-- DISTORTION IS WORST EARLY, WHICH IS WHEN THE SITE IS BEING READ.
--
-- ⚠️ THE TRADE IS REAL AND IT IS MARC'S CALL, WHICH HE MADE: *"probably need to include both
-- sides of a game involving an FBS school."* 80 non-FBS teams enter the 2026 pool, for 85
-- team-games, and they move week 1's p25 from 322.0 to 244.5. The alternative that also closes
-- the pool — FBS-VS-FBS GAMES ONLY — was measured and rejected: it discards 29.8% of this
-- season's real FBS team-games, and its median (367.0) is the same number this rule produces.
--
-- 🚨 CLOSURE IS WHY EVERY JOIN BELOW IS GAME-LEVEL OR OUTER. Three separate row-level joins could
-- each drop one side of a pair and reopen the defect, and two of them measurably would:
--
--     join dim_team  (per team)   62 completed team-games in 2025 and 52 in 2026 have NO
--                                 dim_team row at all, so an inner join drops them and leaves
--                                 their mirrors behind. The classification is now asked of the
--                                 GAME and no per-team join survives.
--     join advanced  (per team)   symmetric today (0 one-sided rows in 2025 or 2026) and nothing
--                                 guarantees it stays that way. LEFT, so a missing advanced row
--                                 costs twelve NULL values and not a row.
--
-- ✅ AND NULLS CANNOT BREAK THE INVARIANT, WHICH IS WHY THE OUTER JOIN IS FREE. The pool is a set
-- P of team-games and `mirror` is a bijection P -> P, so {value(x) : x in P} and
-- {value(mirror(x)) : x in P} are the same multiset whatever the values are — NULLs included.
-- MIRROR CLOSURE IS NECESSARY AND SUFFICIENT; nothing about the values matters.
-- 📊 Measured over every season: 166,298 pool rows, 0 without a mirror.
--
-- ⚠️ `is_completed` IS A GAME-GRAIN FACT and `assert_game_grain_facts_are_equal_across_a_games_two_rows`
-- is what keeps it one — so filtering on it cannot split a pair. `has_box_score` is NOT, and is
-- deliberately not filtered on here: it is one-sided by design, and excluding on it would drop
-- one half of a pair to save a NULL the percentiles already ignore.
--
-- ⚠️ WHAT THE OLD TEST SAID, BECAUSE IT WAS NOT WRONG. `assert_box_score_distribution_uses_the_fbs_population`
-- argued that "a reader comparing an FBS team's 180 rushing yards against a distribution that
-- includes Division II opponents is told they had an ordinary game when they had a good one."
-- ✅ THAT CONCERN SURVIVES AND IS ANSWERED RATHER THAN DISMISSED: the old pool was not the clean
-- FBS one it reads as — it already carried every FBS blowout OF an FCS side, and only the
-- flattering half of it. This rule adds the other half. The test is rewritten, not deleted.
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
with fbs_games as (

    -- THE POPULATION RULE, ASKED ONCE OF THE GAME. `bool_or` over the game's two rows rather
    -- than a `distinct` over a filtered set, because the question is a property of the fixture:
    -- does EITHER side belong to the FBS. The join back below is then on `game_id` alone, so it
    -- cannot express a preference between the two sides and cannot drop one of them.
    select t.game_id
    from {{ ref('fct_game_team') }} t
    left join {{ ref('dim_team') }} d
      on d.season = t.season and d.team_id = t.team_id
    where t.is_completed
    group by t.game_id
    having bool_or(d.classification = 'fbs')

)

select
    t.season, t.season_type, t.week, t.game_id, t.team_id,
    v.metric,
    v.value
from {{ ref('fct_game_team') }} t
join fbs_games g
  on g.game_id = t.game_id
left join {{ ref('fct_game_team_advanced') }} a
  on a.game_team_sk = t.game_team_sk
cross join lateral (values
    {% for metric in metrics %}
    (cast('{{ metric }}' as {{ dbt.type_string() }}),
     cast({{ metric }} as {{ dbt.type_numeric() }})){{ "," if not loop.last }}
    {% endfor %}
) as v(metric, value)
where t.is_completed
