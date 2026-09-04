-- The long form of the histogram: one row per bin. For anything that wants rows rather than
-- a picture — a pivot table, the Excel export, a test that checks exhaustiveness without
-- parsing a string.
--
-- Kept as its own serving view rather than left in marts because the export reads the serving
-- layer only, and a sheet that reached into marts would bypass the boundary every other sheet
-- respects.

select
    season,
    season_type,
    week,
    span,
    metric,
    as_of_date,
    bin_index,
    bin_lower,
    bin_upper,
    games,
    bin_min,
    bin_max,
    bin_incr,
    bin_count,
    as_of_ts
from {{ ref('fct_week_metric_distribution_bin') }}
