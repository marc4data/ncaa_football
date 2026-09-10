-- ONE ROW, ONE AXIS. The shape of a week's FBS team-yardage figures, so every matchup preview
-- in that week can be drawn against the same scale (G-2: a page reads one relation, one pass).
--
-- Marc: "I'd like to standardize axis across all the FBS matchups for the week."
--
-- ⚠️ THIS IS A THIN PASS-THROUGH AND THAT IS DELIBERATE. Its sibling
-- srv_week_metric_distribution flattens a companion bin table into a delimited string, because
-- a histogram needs per-bin counts. THIS object's consumer is a SCATTER AXIS: it needs limits,
-- a tick step and reference bands, all of which are scalars. Building a bin table with no
-- reader would be the R-492 class — an object published and never consumed — so the histogram
-- half is deliberately absent until something draws one.
--
-- WHAT A PAGE DOES WITH IT: axis_min/axis_max/axis_step give the shared frame and its labelled
-- ticks; p05/p95 (or mean ± stddev) give Marc's "visual reference to extreme performers";
-- whisker_low/high and outlier_count give the box-whisker if the standard's card is drawn.
--
-- ⚠️ NO ROW FOR WEEK 1. The per-game figures lead INTO the week, so at week 1 every team's is
-- NULL by design and there is no distribution to describe. The absence is the honest answer and
-- states.render_or_state turns it into an Empty state.

select
    d.season,
    d.season_type,
    d.week,
    d.metric,
    d.n,
    d.teams_in_week,
    d.min_games_counted,
    d.max_games_counted,
    d.mean,
    d.stddev,
    d.min_value,
    d.max_value,
    d.p02, d.p05, d.p25, d.p50, d.p75, d.p95, d.p98,
    d.iqr,
    d.whisker_low,
    d.whisker_high,
    d.outlier_count,
    d.axis_min,
    d.axis_max,
    d.axis_step,
    ao.as_of_ts
from {{ ref('fct_team_week_metric_distribution') }} d
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
