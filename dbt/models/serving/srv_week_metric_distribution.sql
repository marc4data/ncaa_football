-- ONE ROW, ONE PICTURE. Everything a distribution chart draws, flattened so a page reads a
-- single relation in a single pass (G-2).
--
-- THE BIN COUNTS ARRIVE AS A DELIMITED STRING, and the reason is dialect portability rather
-- than taste. dbt here dispatches the same models onto Postgres and Databricks; array types
-- and their aggregate functions differ between them, and this project has one portability
-- macro layer, not two. A '12,31,44,...' string parsed by the renderer is ugly and works
-- identically on both.
--
-- Fixed columns bin_01..bin_10 were the alternative — typed, portable, and rigid about the
-- bin count forever. The bin count is measured (R-197) and could move if the weekly n does;
-- freezing it into ten column names would make that a migration.
--
-- The long form stays available as `srv_week_metric_distribution_bin` for anything that wants
-- rows — the Excel export will.

with bins as (
    select
        season, season_type, week, span, metric, as_of_date,
        -- ORDER BY INSIDE THE AGGREGATE. Without it the string's order is whatever the
        -- engine returns, and a histogram drawn from shuffled counts is wrong in a way that
        -- looks plausible — the shape changes, nothing errors, and no test that only sums
        -- the counts would notice.
        string_agg(cast(games as {{ dbt.type_string() }}), ',' order by bin_index) as bin_counts
    from {{ ref('fct_week_metric_distribution_bin') }}
    group by season, season_type, week, span, metric, as_of_date
)

select
    d.season,
    d.season_type,
    d.week,
    d.span,
    d.metric,
    d.as_of_date,

    d.games_in_week,
    d.n,
    d.coverage_pct,
    d.games_locked,
    d.games_live,
    d.is_locked,
    d.excluded_indoor,

    d.mean,
    d.stddev,
    d.min_value,
    d.max_value,
    d.p02, d.p05, d.p25, d.p50, d.p75, d.p95, d.p98,
    d.iqr,
    d.whisker_lo,
    d.whisker_hi,
    d.outlier_count,

    d.bin_min,
    d.bin_max,
    d.bin_incr,
    d.bin_count,
    d.below_min_count,
    d.above_max_count,
    b.bin_counts,

    d.as_of_ts

from {{ ref('fct_week_metric_distribution') }} d
left join bins b
       on  b.season = d.season and b.season_type = d.season_type
       and b.week = d.week and b.span = d.span
       and b.metric = d.metric and b.as_of_date = d.as_of_date
