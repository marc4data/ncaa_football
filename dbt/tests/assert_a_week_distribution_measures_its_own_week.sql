-- A214. A `week`-SPAN DISTRIBUTION MEASURES THAT WEEK'S GAMES AND NO OTHERS.
--
-- 🚨 THE GRAIN IS THE THING MOST LIKELY TO BE WRONG AND LEAST LIKELY TO LOOK WRONG. Widening
-- the membership join by one character - `w.week = l.week` to `w.week >= l.week` - turns every
-- week's percentiles into season-to-date percentiles. Every value stays plausible, every
-- percentile stays monotonic, the whiskers stay inside the data, and `n` still never exceeds
-- `games_in_week` because BOTH sides of that comparison grow together. 📊 A214 staged exactly
-- that break and `assert_a_distribution_never_counts_more_than_it_measured` stayed green.
--
-- ✅ WHAT SEES IT IS AN OUTSIDE NUMBER: `games_in_week` on a `week` row must equal the games
-- that week, counted independently from `int_week_metric_value` rather than read off the same
-- aggregation. The break inflates the first and cannot touch the second.
--
-- 🚨 AND THE COUNT COMES FROM `int_week_metric_value`, NOT FROM `srv_game`, FOR A REASON THE
-- SUITE HAD TO TELL ME. The obvious version of this test counted FBS games in `srv_game` - a
-- true statement, and it agreed on all 346 rows - and
-- `test_no_test_straddles_the_gated_dags_refresh_boundary` failed it: `cfbd_lines_snapshot`
-- rebuilds `fct_week_metric_distribution` and does NOT rebuild `srv_game`, so the test would
-- run against one fresh relation and one stale one and go red for a reason that is not a
-- defect. ⚠️ Both relations must sit on ONE cadence, and `int_week_metric_value` is the
-- distribution's own parent, so it is rebuilt by every DAG that rebuilds the distribution.
--
-- ⚠️ `season_to_date` ROWS ARE DELIBERATELY NOT CHECKED HERE. Their population is every EARLIER
-- week, so they are supposed to exceed the week's own count; asserting one rule over both spans
-- would be the R-2455 shape - a bound loose enough to hold for the wrong reason.
--
-- ⚠️ BOTH RELATIONS ARE `ref()`ed (§3.6), so this is ordered after them rather than free to run
-- before either exists, and it names no week and no game (§2.3.3) so it says the same true
-- thing about CI's fixture sample as about the warehouse.
with expected as (
    -- One row per (game, metric, as_of_date) there, so the week's game count is a DISTINCT
    -- count of game_id. The FBS-either-side population is applied in that model, once.
    select season, season_type, week, as_of_date,
           count(distinct game_id) as games_that_week
    from {{ ref('int_week_metric_value') }}
    group by season, season_type, week, as_of_date
)

select
    d.season, d.season_type, d.week, d.metric, d.as_of_date,
    d.games_in_week,
    e.games_that_week
from {{ ref('fct_week_metric_distribution') }} d
join expected e
  on  e.season = d.season and e.season_type = d.season_type and e.week = d.week
  and e.as_of_date = d.as_of_date
where d.span = 'week'
  and d.games_in_week is distinct from e.games_that_week
