-- A percentile series that goes backwards is not a distribution.
--
-- Cheap to check and impossible to eyeball on 450 rows: a box plot drawn from p25 > p75
-- renders a box of negative width, which most renderers silently clamp to zero — so the
-- picture looks like a tight distribution rather than like a bug.
select season, season_type, week, span, metric, as_of_date,
       min_value, p02, p05, p25, p50, p75, p95, p98, max_value
from {{ ref('fct_week_metric_distribution') }}
where not (min_value <= p02 and p02 <= p05 and p05 <= p25 and p25 <= p50
           and p50 <= p75 and p75 <= p95 and p95 <= p98 and p98 <= max_value)
