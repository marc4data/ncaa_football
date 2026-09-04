-- A LOCKED WEEK STOPS ACCUMULATING ROWS.
--
-- Once the last game of a week has kicked off, the numbers can never change again, so every
-- later run would write an identical row. Left unguarded, a finished season grows a new row
-- per metric per day for eight months — 6 metrics x 2 spans x 16 weeks x 240 days is roughly
-- 46,000 rows that all say the same thing.
--
-- The guard is `and not exists (... and prior.is_locked)` in both facts. This asserts the
-- outcome rather than the clause: at most ONE locked snapshot per grain.
--
-- More than one is not automatically wrong in history — a week can have several unlocked
-- daily rows and then one locked one. So the count is of LOCKED rows only.
select season, season_type, week, span, metric, count(*) as locked_snapshots
from {{ ref('fct_week_metric_distribution') }}
where is_locked
group by season, season_type, week, span, metric
having count(*) > 1
