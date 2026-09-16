{{ config(materialized='table') }}

-- The shape of the SEASON SO FAR, at single-game team grain, for a page that has to draw a
-- fixture nobody has played yet. A143, cfdb-main-R-973.
-- One row per (season, season_type, week, metric): every team-game played in weeks strictly
-- before this one.
--
-- 🚨 THIS IS THE RELATION A PREVIEW READS. Its single-week sibling cannot serve one and that is
-- structural rather than a gap: a single-game observation belongs to the week it was PLAYED in,
-- so an unplayed week has no row. 📊 Measured on live serving before this view existed: for 2026
-- the sibling served regular weeks 1 and 2 and nothing else, against **2,924 unplayed regular
-- games**. A week-3 matchup preview asked it for a distribution and got zero rows — and would
-- have rendered six titled em dashes with every "the chart is present" assertion still passing.
--
-- 🚨 THE FOURTH IN THE FAMILY, AND NOW TWO THINGS TELL THEM APART RATHER THAN ONE:
--
--     srv_week_metric_distribution        GAME grain      the week          spread, total, temp
--     srv_team_week_metric_distribution   TEAM            cumulative AVGS   6 per-game averages
--     srv_game_team_metric_distribution   TEAM, ONE GAME  the week          18 box/advanced
--     THIS VIEW                           TEAM, ONE GAME  cumulative OBS    18 box/advanced
--
-- ⚠️ THE GRAIN IS IDENTICAL TO THE THIRD AND ONLY THE WINDOW DIFFERS, which is exactly why the
-- name carries the window (§4.3). `_through_prior_week` is the project's existing word for this —
-- `srv_game_team_leader_through_prior_week` is already in the registry and
-- `fct_player_leader_week` publishes `yards_through_prior_week`.
--
-- ✅ SAME PERCENTILE VOCABULARY AS ALL THREE SIBLINGS — p02 p05 p25 p50 p75 p95 p98, iqr,
-- whiskers, outlier_count — so `lib/distribution.box()` draws it with no change at all. That is
-- Marc's "consistent method... applied to the all/subset of the population", and it is why that
-- function takes a ROW rather than a metric name.
--
-- ⚠️ `weeks_counted` RATHER THAN A SECOND COUNT, and the mart's header carries the argument: the
-- window is built from observations, so `n` already IS the number of team-games the box is drawn
-- from. What a reader cannot otherwise know is how much football that is — one week or eleven —
-- and that is the denominator that actually travels with the numerator here (AC-G.33).
--
-- 🚨 ONE CONSEQUENCE, STATED RATHER THAN LEFT TO BE DISCOVERED: `lib/distribution.describe()`
-- looks its denominator up by candidate name — `team_games_in_week`, `teams_in_week`,
-- `games_in_week` — and this view publishes none of them, so its tooltip reads `n=370` instead of
-- `n=370 of 370 team-games`. ⚠️ THAT IS A DEGRADATION AND NOT A FAULT: the count is still there and
-- still correct, and the renderer was deliberately left untouched this round. Adding
-- `("weeks_counted", "weeks")` to that candidate list is a one-line change for whoever owns the
-- renderer next.
--
-- ⚠️ WEEK 1 HAS NO ROW, which is the honest answer rather than an omission: there is nothing
-- before it. The page's existing empty-state wording covers it unchanged.
select
    d.game_team_metric_distribution_through_prior_week_sk,
    d.season,
    d.season_type,
    d.week,
    d.metric,
    d.n,
    d.weeks_counted,
    d.mean,
    d.stddev,
    d.min_value,
    d.max_value,
    d.p02,
    d.p05,
    d.p25,
    d.p50,
    d.p75,
    d.p95,
    d.p98,
    d.iqr,
    d.whisker_low,
    d.whisker_high,
    d.outlier_count,
    ao.as_of_ts
from {{ ref('fct_game_team_metric_distribution_through_prior_week') }} d
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
