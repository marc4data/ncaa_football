-- R-642. AN EIGHTH OF A YARDAGE FRAME USED TO SIT BELOW ZERO.
--
-- `rushing_yards_allowed_per_game` carried axis_min = -50 on 14 rows, because min_value is -7.0:
-- SACKS COUNT AGAINST RUSHING, so a team one game into a season can genuinely concede a negative
-- rushing average. ⚠️ The -7.0 is legitimate data and it survives — see
-- assert_the_distribution_does_not_clamp_the_values_it_describes.sql, which is the other half of
-- this pair. What was wrong was spending an eighth of every matchup's shared frame on territory
-- a single team occupies.
--
-- B084 argued the same thing from the band rather than the axis a week earlier: a ±1σ band at
-- week 2 "extends below zero, which is not a yardage." Same conclusion, second route.
--
-- 🚨 ALL SIX METRICS IN THIS MODEL ARE YARDS PER GAME, which is the assumption that lets the
-- floor be a flat zero instead of a per-metric setting. If a signed metric is ever added to the
-- model's `metrics` list, this test fails and that is the point: the floor becomes a decision
-- again rather than an inherited default.
select season, season_type, week, metric, axis_min, axis_max, whisker_low, min_value
from {{ ref('fct_team_week_metric_distribution') }}
where axis_min < 0
