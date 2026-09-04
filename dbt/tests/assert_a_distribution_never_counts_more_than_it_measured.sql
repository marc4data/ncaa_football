-- `n` is games WITH A VALUE; `games_in_week` is games in scope. A rate without its
-- denominator is the defect AC-G.33 exists to prevent, and it is worse here than anywhere: a
-- temperature distribution over the 9 games of a week that had weather looks identical to one
-- over 124 games, and the median it reports is a different claim entirely.
--
-- So both travel on the row, and this asserts the pair is coherent.
select season, season_type, week, span, metric, as_of_date, n, games_in_week, coverage_pct
from {{ ref('fct_week_metric_distribution') }}
where n > games_in_week
   or n < 0
   or games_in_week < 0
   or (coverage_pct is not null and (coverage_pct < 0 or coverage_pct > 100))
