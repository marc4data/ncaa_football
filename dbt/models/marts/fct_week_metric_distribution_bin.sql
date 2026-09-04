{{ config(
    materialized='incremental',
    unique_key='week_metric_distribution_bin_sk',
    incremental_strategy='append'
) }}

-- HOW MANY GAMES FELL IN EACH BIN. One row per
-- (season, season_type, week, span, metric, as_of_date, bin_index).
--
-- The long form, and the source of truth for the counts. `srv_week_metric_distribution`
-- pivots it onto the summary row so a page reads ONE relation (G-2); this stays the testable
-- object, and the Excel export will want it as-is because the long form is what a pivot table
-- wants.
--
-- EVERY BIN IS EMITTED, INCLUDING THE EMPTY ONES. A sparkline with a gap where a bin had no
-- games is a different picture from one with a short bar, and a renderer that has to infer
-- missing indices will eventually infer them wrong. The cross join is what guarantees ten
-- rows per metric per week whatever the data does.
--
-- HALF-OPEN BINS, [lo, hi), with the LAST bin closed so the maximum lands somewhere. Without
-- that, a value exactly equal to bin_max falls outside every bin and the exhaustiveness test
-- fails on the one game that touched the ceiling.

{% set bin_count = var('distribution_bin_count') %}
{% set bins = var('distribution_bins') %}

with long as (
    select * from {{ ref('int_week_metric_value') }}
),

weeks as (
    select distinct season, season_type, week, as_of_date from long
),

membership as (
    -- The same two spans as the summary fact, and they MUST be the same: a bin count that
    -- disagrees with the n beside it is the exhaustiveness test failing, which is the single
    -- most valuable check here.
    select l.metric, l.value, w.season, w.season_type, w.week, w.as_of_date,
           cast('week' as {{ dbt.type_string() }}) as span
    from long l
    join weeks w
      on  w.season = l.season and w.season_type = l.season_type
      and w.as_of_date = l.as_of_date and w.week = l.week
    union all
    select l.metric, l.value, w.season, w.season_type, w.week, w.as_of_date,
           cast('season_to_date' as {{ dbt.type_string() }}) as span
    from long l
    join weeks w
      on  w.season = l.season and w.season_type = l.season_type
      and w.as_of_date = l.as_of_date and l.week < w.week
),

edges as (
    {% for metric, cfg in bins.items() %}
    select '{{ metric }}' as metric,
           cast({{ cfg['min'] }} as numeric) as bin_min,
           cast({{ cfg['max'] }} as numeric) as bin_max,
           cast({{ bin_count }} as integer)  as bin_count
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

indexes as (
    select generate_series(1, {{ bin_count }}) as bin_index
),

frame as (
    -- Every (week, metric, bin) that should exist, before any counting.
    select distinct
        l.season, l.season_type, l.week, l.span, l.as_of_date, l.metric,
        e.bin_min, e.bin_max, e.bin_count,
        (e.bin_max - e.bin_min) / e.bin_count as bin_incr,
        i.bin_index
    from membership l
    join edges e on e.metric = l.metric
    cross join indexes i
    where l.value is not null
),

counted as (
    select
        f.season, f.season_type, f.week, f.span, f.as_of_date, f.metric,
        f.bin_index, f.bin_min, f.bin_max, f.bin_count, f.bin_incr,
        f.bin_min + (f.bin_index - 1) * f.bin_incr as bin_lower,
        f.bin_min + f.bin_index * f.bin_incr       as bin_upper,
        count(l.value)                             as games
    from frame f
    left join membership l
      on  l.season = f.season and l.season_type = f.season_type
      and l.week = f.week and l.span = f.span
      and l.as_of_date = f.as_of_date and l.metric = f.metric
      and l.value is not null
      and l.value >= f.bin_min + (f.bin_index - 1) * f.bin_incr
      and (l.value <  f.bin_min + f.bin_index * f.bin_incr
           -- the last bin is closed, so bin_max itself lands in it
           or (f.bin_index = f.bin_count and l.value = f.bin_max))
    group by f.season, f.season_type, f.week, f.span, f.as_of_date, f.metric,
             f.bin_index, f.bin_min, f.bin_max, f.bin_count, f.bin_incr
)

select
    {{ surrogate_key([
        'season', 'season_type', 'week', 'span', 'metric', 'as_of_date', 'bin_index'
    ]) }}                                   as week_metric_distribution_bin_sk,
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
    bin_count,
    bin_incr,
    {{ dbt.current_timestamp() }}           as as_of_ts
from counted c

{% if is_incremental() %}
where not exists (
    select 1 from {{ this }} prior
    where prior.season = c.season
      and prior.season_type = c.season_type
      and prior.week = c.week
      and prior.span = c.span
      and prior.metric = c.metric
      and prior.as_of_date = c.as_of_date
)
{% endif %}
