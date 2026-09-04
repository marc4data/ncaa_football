-- WHISKERS REACH AN OBSERVATION, NOT A FORMULA.
--
-- matplotlib's `whis=1.5` convention — which `plot_distribution` uses and which this model
-- reproduces — puts the whisker at the most extreme value still WITHIN 1.5*IQR of the box.
-- The naive reading computes q1 - 1.5*IQR and draws the whisker there, which produces
-- whiskers extending past the data. That looks like a bug and is one.
--
-- Also asserts the box is inside the whiskers, which the naive form gets right and a
-- transposed pair of columns would not.
select season, season_type, week, span, metric, as_of_date,
       min_value, whisker_lo, p25, p75, whisker_hi, max_value
from {{ ref('fct_week_metric_distribution') }}
where whisker_lo < min_value
   or whisker_hi > max_value
   or whisker_lo > p25
   or whisker_hi < p75
