{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only`, AND THE CHECK THAT DEMANDED IT WAS RIGHT. This test reconciles
-- fct_team_week_metric_distribution against fct_team_yardage_week, and cfbd_scores_refresh
-- rebuilds the SECOND of those every two hours without rebuilding the first. Between those two
-- moments the distribution legitimately describes an earlier refresh, so an untagged version
-- would go red on a game day for a reason that is not the defect — and because
-- publish_to_serving sits downstream of dbt_test on all_success, it would STOP THE SITE
-- UPDATING rather than merely report a false problem. ci/check_test_refresh_scope.py caught
-- this on its first run against the new test. Full authority on the weekly +tag:production
-- build, which rebuilds both sides.
-- 🚨 CLAMP THE AXIS, NEVER THE VALUE. R-642's other half.
--
-- The obvious way to stop an axis going below zero is to stop the DATA going below zero, and it
-- is wrong: -7.0 rushing yards allowed per game is a real measurement — sacks count against
-- rushing — and a model that quietly turns it into 0.0 has lost a fact to fix a frame. That is
-- worse than the defect, because the frame is visibly odd and the lost value is not.
--
-- ⚠️ SO THIS RECONCILES min_value AND max_value BACK TO THE SOURCE rather than asserting a
-- range. A `greatest(0, value)` anywhere between fct_team_yardage_week and here moves min_value
-- off the true minimum and this test names the metric and both numbers.
--
-- Reads the same FBS spine the model reads (dim_team.classification), one layer down, because a
-- test built over a different population would fail for a reason that is not the defect.
{% set metrics = [
    'total_yards_for_per_game', 'total_yards_allowed_per_game',
    'rushing_yards_for_per_game', 'rushing_yards_allowed_per_game',
    'passing_yards_for_per_game', 'passing_yards_allowed_per_game'
] %}
-- ⚠️ ONE GROUPED PASS AND NO UNION, AND THAT IS NOT A STYLE CHOICE. The first version of this
-- test unioned the six metrics into a long frame and aggregated that — six scans of
-- fct_team_yardage_week where one will do. On the droplet it went parallel and died with
-- `could not resize shared memory segment ... No space left on device`: the warehouse container
-- has a small /dev/shm, so a plan that asks for a large parallel hash fails on infrastructure
-- rather than on data. A test that errors is worse than no test, because it blocks the build
-- while proving nothing. Six min/max pairs off a single grouped scan cost a fraction of that.
with source_extremes as (
    select y.season, y.season_type, y.week
           {% for metric in metrics %}
           , min(cast(y.{{ metric }} as {{ dbt.type_numeric() }})) as min_{{ metric }}
           , max(cast(y.{{ metric }} as {{ dbt.type_numeric() }})) as max_{{ metric }}
           {% endfor %}
    from {{ ref('fct_team_yardage_week') }} y
    join {{ ref('dim_team') }} d
      on d.season = y.season and d.team_id = y.team_id
    where d.classification = 'fbs'
    group by y.season, y.season_type, y.week
)
select d.season, d.season_type, d.week, d.metric,
       d.min_value, d.max_value
from {{ ref('fct_team_week_metric_distribution') }} d
join source_extremes s
  on s.season = d.season and s.season_type = d.season_type and s.week = d.week
where
{% for metric in metrics %}
    (d.metric = '{{ metric }}' and (d.min_value <> s.min_{{ metric }}
                                 or d.max_value <> s.max_{{ metric }}))
    {{ "or" if not loop.last }}
{% endfor %}
