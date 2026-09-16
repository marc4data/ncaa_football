{{ config(materialized='table') }}

-- THE SHAPE OF A WEEK'S BOX SCORES, AT SINGLE-GAME TEAM GRAIN. R-808.
-- One row per (season, season_type, week, metric).
--
-- Marc, 2026-09-14: "For every measure I'd like a horizontal box-whisker plot under the measure
-- value... Use consistent method for evaluating how to present measures so that we can apply it
-- to the all/subset of the population."
--
-- 🚨 A THIRD SIBLING, AND THE GRAIN IS WHY — THIS PROJECT HAS MADE THIS ARGUMENT TWICE ALREADY.
--
--     fct_week_metric_distribution        GAME grain. One spread, one total, one temperature
--                                         per fixture. Carries `span` (week / season_to_date)
--                                         and an `as_of_date` lock, because a line reprices all
--                                         week.
--     fct_team_week_metric_distribution   TEAM grain, CUMULATIVE. srv_team_week's per-game
--                                         averages, which lead INTO a week and are already
--                                         to-date.
--     THIS MODEL                          TEAM grain, SINGLE GAME. What one team did in one
--                                         game — the numbers Box Score and Advanced actually
--                                         render.
--
-- ⚠️ THE SECOND MODEL'S HEADER ALREADY REFUSED TO ABSORB A DIFFERENT GRAIN, in these words: "a
-- SIBLING at a different grain, NOT an extension of it... sharing the model would have meant a
-- `grain` column that half the rows answer differently. Two models, one vocabulary." The same
-- sentence applies here, and for a second reason: its values are AVERAGES ACROSS GAMES and
-- these are SINGLE-GAME observations. Mixing them under one `metric` column would put two
-- definitions of "rushing yards" side by side, and the box plot a reader sees would describe a
-- population that is not the one the number above it came from.
--
-- ✅ PERCENTILES NEED NO BIN RANGE, AND THAT IS NOT A HYPOTHESIS — IT IS ALREADY SHIPPED.
-- `distribution_bins` in dbt_project.yml carries SIX game-grain metrics and none of these, and
-- `fct_team_week_metric_distribution` has computed p02 through p98, whiskers and outlier counts
-- for six metrics with no bin entry since it was built. Bins belong to the HISTOGRAM, which
-- needs a hand-set {min, max}; a box plot is computed from the values. So "every measure" is
-- reachable without eighteen hand-tuned ranges, and this model sets none.
--
-- ⚠️ THE POPULATION RULE IS READ, NOT REIMPLEMENTED. It lives in `int_game_team_metric_value`
-- and nothing here restates it — a second copy of a population rule is the drift this project has
-- paid for repeatedly.
--
-- 🚨 AND A142 CHANGED IT: the pool is now every team-game of a COMPLETED GAME INVOLVING AN FBS
-- SCHOOL, both sides, rather than every FBS team's team-game. The intermediate's header carries
-- the measurement and the argument; what matters HERE is the property it buys.
--
-- ✅ THE POOL IS CLOSED UNDER `mirror`, AND THAT MAKES MARC'S INVARIANT AN IDENTITY.
-- For any metric M, a team-game's "allowed M" is its opponent's M in the same game. `mirror` is a
-- bijection on the pool, so the multiset of allowed values IS the multiset of gained values —
-- every percentile, the mean, the whiskers, the outlier count, all of them, exactly.
--
-- 📊 MEASURED BOTH WAYS ON `total_yards`: 2026 regular, p25/p50/p75 = 255.5 / 367.0 / 474.75 for
-- gained AND for allowed; 2025 regular, 295.0 / 375.0 / 452.25 for both. Under the OLD population
-- the same two columns read 398.0 and 322.0 at the median.
--
-- 🚨 SO A PAGE DRAWING GAINED AND ALLOWED AT THIS GRAIN DRAWS ONE DISTRIBUTION TWICE, and that is
-- the correct picture rather than a redundancy: what differs between the two charts is where the
-- TEAM's own marks fall on it, which is the comparison the reader came for.
-- `assert_gained_and_allowed_match_at_game_grain` is what keeps it true.
--
-- ⚠️ THIS PROPERTY DOES NOT HOLD ONE MODEL OVER, AND IT CANNOT. See design note 6 in
-- `fct_team_week_metric_distribution`: season-to-date AVERAGES break the pairing even in a
-- perfectly closed league, measured.
--
-- ⚠️ NO `as_of_date` AND NO LOCK RULE, for the second model's reason rather than by omission: a
-- completed game's box score does not reprice. `fct_week_metric_distribution` needs the lock
-- because a spread moves all week; nothing here moves once the whistle goes.
--
-- ⚠️ NO `span`, either. A single-game observation belongs to the week it was played in, and a
-- `season_to_date` span over single-game values would be a different question ("every game so
-- far") that this model can answer by widening the group later if anyone asks for it. Left out
-- rather than shipped inert — the second model's own rule.
--
-- ⚠️ AC-G.11: `n` IS PUBLISHED SO A READER CAN TELL "TOO FEW TO SAY" FROM "NONE". A week with
-- one observation has no distribution and gets no row (the `having` below); a week with eight
-- has a row and a small `n`, and the page decides what to draw. Those are three different
-- states and only the middle one is a judgement call.
with long as (

    -- The per-team-game values, from the ONE model that computes them. The FBS rule and the
    -- mart join live there. ⚠️ AND IT IS A TABLE RATHER THAN A CTE BECAUSE THIS MODEL REFERENCES
    -- IT TWICE — once for the percentiles and once for the whisker pass — and four million rows
    -- materialised inside a query exhausted /dev/shm. Its header carries the error.
    select * from {{ ref('int_game_team_metric_value') }}

),

per_week as (

    select
        season, season_type, week, metric,
        count(value)                                        as n,
        count(*)                                            as team_games_in_week,
        avg(value)                                          as mean,
        stddev_samp(value)                                  as stddev,
        min(value)                                          as min_value,
        max(value)                                          as max_value,
        percentile_cont(0.02) within group (order by value) as p02,
        percentile_cont(0.05) within group (order by value) as p05,
        percentile_cont(0.25) within group (order by value) as p25,
        percentile_cont(0.50) within group (order by value) as p50,
        percentile_cont(0.75) within group (order by value) as p75,
        percentile_cont(0.95) within group (order by value) as p95,
        percentile_cont(0.98) within group (order by value) as p98
    from long
    group by season, season_type, week, metric
    -- One observation is not a distribution. No row rather than a box with no width.
    having count(value) > 1

),

spread_stats as (

    select p.*,
           p75 - p25                        as iqr,
           p25 - 1.5 * (p75 - p25)          as lower_fence,
           p75 + 1.5 * (p75 - p25)          as upper_fence
    from per_week p

),

whiskers as (

    -- 🚨 ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW. A097 measured the cost of the
    -- other shape on this exact family of models: 0.9s against 65.5s, the same subqueries,
    -- seventy times the work, purely from where their output was referenced. The sibling model
    -- carries the full post-mortem.
    select s.*,
           b.whisker_low,
           b.whisker_high,
           coalesce(b.outlier_count, 0)                     as outlier_count
    from spread_stats s
    left join (
        select l.season, l.season_type, l.week, l.metric,
               -- Tukey, and the convention both sibling models state: the whisker reaches the
               -- most extreme OBSERVATION still inside 1.5*IQR, never the fence itself. A fence
               -- drawn as a whisker is longer than the data and reads as a value nobody
               -- recorded.
               min(case when l.value >= f.lower_fence then l.value end) as whisker_low,
               max(case when l.value <= f.upper_fence then l.value end) as whisker_high,
               sum(case when l.value < f.lower_fence
                         or l.value > f.upper_fence then 1 else 0 end)  as outlier_count
        from long l
        join spread_stats f
          on f.season = l.season and f.season_type = l.season_type
         and f.week = l.week and f.metric = l.metric
        group by l.season, l.season_type, l.week, l.metric
    ) b
      on b.season = s.season and b.season_type = s.season_type
     and b.week = s.week and b.metric = s.metric

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'metric']) }} as game_team_metric_distribution_sk,
    season,
    season_type,
    week,
    metric,
    n,
    team_games_in_week,
    -- ⚠️ PUBLISHED UNROUNDED, MATCHING BOTH SIBLING MODELS. `percentile_cont` returns double
    -- precision and neither `fct_week_metric_distribution` nor `fct_team_week_metric_distribution`
    -- rounds its percentiles; the page formats. Rounding here would make this the one model of
    -- three with a different convention, which is how one vocabulary becomes two.
    mean,
    stddev,
    min_value,
    max_value,
    p02, p05, p25, p50, p75, p95, p98,
    iqr,
    whisker_low,
    whisker_high,
    outlier_count
from whiskers
