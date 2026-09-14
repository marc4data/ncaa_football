{{ config(materialized='table') }}

-- The shape of a week's BOX SCORES, at single-game team grain, for the page. R-808.
-- One row per (season, season_type, week, metric).
--
-- Marc: "For every measure I'd like a horizontal box-whisker plot under the measure value...
-- Use consistent method for evaluating how to present measures so that we can apply it to the
-- all/subset of the population."
--
-- 🚨 THE THIRD DISTRIBUTION IN THE FAMILY, AND THE THREE ARE SIBLINGS RATHER THAN VERSIONS:
--
--     srv_week_metric_distribution        GAME grain      spread, total, temperature — 6
--     srv_team_week_metric_distribution   TEAM, CUMULATIVE per-game averages to date — 6
--     THIS VIEW                           TEAM, ONE GAME  what Box Score and Advanced render — 18
--
-- ✅ ALL THREE PUBLISH THE SAME PERCENTILE VOCABULARY — p02 p05 p25 p50 p75 p95 p98, iqr,
-- whiskers, outlier_count — which is what makes ONE renderer able to draw any of them. That is
-- Marc's "consistent method... applied to the all/subset of the population", and it is why
-- `lib/distribution.box()` takes a ROW rather than a metric name.
--
-- ⚠️ NO BIN COLUMNS HERE, DELIBERATELY, AND IT IS THE ROUND'S FINDING. `distribution_bins` in
-- dbt_project.yml exists for the HISTOGRAM, which needs a hand-set {min, max} per metric. A BOX
-- PLOT is computed from the values and needs none — which `srv_team_week_metric_distribution`
-- has been proving since it was built, with six metrics and no bin entries. So eighteen measures
-- arrive without eighteen hand-tuned ranges nobody would keep current.
--
-- ⚠️ AC-G.11 — `n` AND `team_games_in_week` TRAVEL SO A PAGE CAN TELL THREE STATES APART:
-- a week with no row at all (fewer than two observations — no distribution exists), a week with
-- a row and a small `n` (a distribution, but a thin one), and a week with a full slate. Only the
-- middle one is a judgement call, and it is the PAGE's to make rather than this model's.
select
    d.game_team_metric_distribution_sk,
    d.season,
    d.season_type,
    d.week,
    d.metric,
    d.n,
    d.team_games_in_week,
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
from {{ ref('fct_game_team_metric_distribution') }} d
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
