-- EVERY BIN IS EMITTED, INCLUDING THE EMPTY ONES.
--
-- A sparkline with a gap where a bin had no games is a different picture from one with a
-- short bar, and a renderer that has to infer which indices are missing will eventually infer
-- them wrong. The bin model cross joins a full index series precisely so this holds; this
-- asserts it did.
--
-- Also pins the count against the configured one rather than against a literal 10, so
-- changing `distribution_bin_count` moves the test with the model.
select season, season_type, week, span, metric, as_of_date, count(*) as bins
from {{ ref('fct_week_metric_distribution_bin') }}
group by season, season_type, week, span, metric, as_of_date
having count(*) <> {{ var('distribution_bin_count') }}
   or count(distinct bin_index) <> {{ var('distribution_bin_count') }}
