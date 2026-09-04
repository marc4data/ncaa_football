-- THE SNAPSHOT HISTORY IS THE FEATURE, AND THIS IS WHAT MAKES IT ONE.
--
-- The models write with `delete+insert` on a surrogate key that CONTAINS as_of_date, which
-- gives three behaviours that have to hold together:
--
--   today's row is REPLACED on every run, so the page tracks the four-hourly cadence
--   an earlier day's row is UNTOUCHED, so "the O/U tightened over four days" stays answerable
--   a LOCKED week is never rewritten at all, so a finished season stops accumulating rows
--
-- The first of those was missing until 2026-09-04: the old guard skipped any week already
-- written today, so the day's first run set the figure and the rest did nothing. On a
-- Saturday that meant the morning's distribution stayed on screen all evening and the week
-- locked a day late.
--
-- What can go wrong now is the opposite — a key that does not include the day would make
-- every run overwrite yesterday, and the history would silently collapse to a single row per
-- week while looking perfectly healthy. That is what this catches: a duplicate on the full
-- grain means the key is not doing its job.
select season, season_type, week, span, metric, as_of_date, count(*) as rows_for_that_day
from {{ ref('fct_week_metric_distribution') }}
group by season, season_type, week, span, metric, as_of_date
having count(*) > 1
