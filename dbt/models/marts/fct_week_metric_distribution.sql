{{ config(
    materialized='incremental',
    unique_key='week_metric_distribution_sk',
    incremental_strategy='append'
) }}

-- THE SHAPE OF ONE WEEK'S MARKET, AS OF ONE DAY. One row per
-- (season, season_type, week, span, metric, as_of_date).
--
-- WHY THIS IS A MODEL AND NOT A HELPER FUNCTION. Every number a distribution chart draws —
-- the percentiles, the bin counts, the box geometry — is an aggregate over a set of games.
-- Computing them in Streamlit means pulling every game row into the page to throw it away,
-- on every rerun, for a picture 120 pixels wide. Precomputing means the page reads ONE ROW.
--
-- It is also the only way Marc's brief is expressible at all: "re-calc each day until
-- kick-off then it's locked". A number computed at render time is computed NOW; he asked for
-- a value computed AS OF A DAY. That is a snapshot, and a snapshot is a table.
--
-- APPEND-ONLY, and the history is the feature: "the O/U distribution for week 3 tightened
-- over four days" is a question this shape answers and a recomputed-on-read view never can.
--
-- THE LOCK RULE, STATED PRECISELY. Kickoff is per GAME and a week's games kick off across
-- three or four days, so a game contributes its CLOSING number once it has started and its
-- LIVE number before that. A mid-slate row is therefore a MIXTURE, which is the honest
-- implementation of what Marc asked for and is why games_locked and games_live are columns:
-- a reader looking at Saturday morning's row needs to know Thursday's game is already sealed
-- into it.
--
-- `is_locked`, not `is_final`. "Final" is already spoken for on this site — it is the Excel
-- header for `is_completed` and it means a game is over. The week band sits directly above
-- cards showing exactly that, and two meanings of "final" on one screen is a defect waiting
-- to be read. `is_locked` is Marc's own word and agrees with games_locked / games_live.
--
-- ONCE LOCKED, NEVER REWRITTEN. A week whose last game has kicked off produces the same row
-- every day forever, so it is written once and then skipped — otherwise a finished season
-- gets a new identical row every night for eight months.

{% set bin_count = var('distribution_bin_count') %}
{% set bins = var('distribution_bins') %}
{% set metrics = bins.keys() | list %}

with long as (
    -- The per-game values, from the ONE model that computes them. The lock rule, the FBS
    -- spine rule and the indoor exclusion all live there, so this model is only aggregation.
    select * from {{ ref('int_week_metric_value') }}
),

weeks as (
    -- Every (week, as_of_date) that could carry a row.
    select distinct season, season_type, week, as_of_date from long
),

membership as (
    -- WHICH GAMES COUNT TOWARDS WHICH ROW. Two spans, one aggregation below.
    --
    -- `week` is the week's own games. `season_to_date` is every EARLIER week in the same
    -- season and season type — strictly earlier, so the reference figure does not contain
    -- the thing being referenced.
    --
    -- That is not a preference: `srv_game`'s own `series` CTE computes the head-to-head
    -- record as it stood BEFORE the current game and excludes the fixture on its own row,
    -- with the reasoning written into the model. Same shape, same answer.
    --
    -- CONSEQUENCE, AND IT IS THE RIGHT ONE: week 1 has no season-to-date row at all. That is
    -- an Empty state rather than a zero, exactly as a week nobody has priced is.
    select l.metric, l.value, l.has_kicked, l.is_indoors, l.game_id,
           w.season, w.season_type, w.week, w.as_of_date,
           cast('week' as {{ dbt.type_string() }}) as span
    from long l
    join weeks w
      on  w.season = l.season and w.season_type = l.season_type
      and w.as_of_date = l.as_of_date and w.week = l.week
    union all
    select l.metric, l.value, l.has_kicked, l.is_indoors, l.game_id,
           w.season, w.season_type, w.week, w.as_of_date,
           cast('season_to_date' as {{ dbt.type_string() }}) as span
    from long l
    join weeks w
      on  w.season = l.season and w.season_type = l.season_type
      and w.as_of_date = l.as_of_date and l.week < w.week
),

per_week as (
    select
        season, season_type, week, span, as_of_date, metric,
        count(*)                                        as games_in_week,
        count(value)                                    as n,
        count(*) filter (where has_kicked)              as games_locked,
        count(*) filter (where not has_kicked)          as games_live,
        count(*) filter (where metric = 'temperature_f' and is_indoors) as excluded_indoor,
        avg(value)                                      as mean,
        stddev_samp(value)                              as stddev,
        min(value)                                      as min_value,
        max(value)                                      as max_value,
        percentile_cont(0.02) within group (order by value) as p02,
        percentile_cont(0.05) within group (order by value) as p05,
        percentile_cont(0.25) within group (order by value) as p25,
        percentile_cont(0.50) within group (order by value) as p50,
        percentile_cont(0.75) within group (order by value) as p75,
        percentile_cont(0.95) within group (order by value) as p95,
        percentile_cont(0.98) within group (order by value) as p98
    from membership
    group by season, season_type, week, span, as_of_date, metric
),

whiskers as (
    -- WHISKERS REACH THE MOST EXTREME OBSERVATION STILL WITHIN 1.5*IQR — matplotlib's
    -- convention, and NOT q1 - 1.5*IQR itself. Getting this wrong produces whiskers that
    -- extend past the data, which looks like a bug and is one.
    select
        l.season, l.season_type, l.week, l.span, l.as_of_date, l.metric,
        min(l.value) filter (where l.value >= w.p25 - 1.5 * (w.p75 - w.p25)) as whisker_lo,
        max(l.value) filter (where l.value <= w.p75 + 1.5 * (w.p75 - w.p25)) as whisker_hi,
        count(*) filter (where l.value < w.p25 - 1.5 * (w.p75 - w.p25)
                            or l.value > w.p75 + 1.5 * (w.p75 - w.p25))      as outlier_count
    from membership l
    join per_week w
      on  w.season = l.season and w.season_type = l.season_type
      and w.week = l.week and w.span = l.span
      and w.as_of_date = l.as_of_date and w.metric = l.metric
    where l.value is not null
    group by l.season, l.season_type, l.week, l.span, l.as_of_date, l.metric
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

tails as (
    select l.season, l.season_type, l.week, l.span, l.as_of_date, l.metric,
           count(*) filter (where l.value < e.bin_min) as below_min_count,
           count(*) filter (where l.value > e.bin_max) as above_max_count
    from membership l
    join edges e on e.metric = l.metric
    where l.value is not null
    group by l.season, l.season_type, l.week, l.span, l.as_of_date, l.metric
)

select
    {{ surrogate_key([
        'w.season', 'w.season_type', 'w.week', 'w.span', 'w.metric', 'w.as_of_date'
    ]) }}                                               as week_metric_distribution_sk,
    w.season,
    w.season_type,
    w.week,

    -- `span`, not `window`: WINDOW is a RESERVED keyword in PostgreSQL — verified against
    -- pg_get_keywords(), catcode 'R' — and a function name in Spark SQL, and this project
    -- dispatches the same models onto both. `period` is taken too: on a football model it
    -- means quarters (home_periods, away_periods).
    w.span,
    w.metric,
    w.as_of_date,

    -- DENOMINATORS, AND THEY ARE NOT OPTIONAL. A temperature distribution over the 9 games of
    -- a week that had weather looks identical to one over 124 games, and the median it
    -- reports is a different claim entirely.
    w.games_in_week,
    w.n,
    case when w.games_in_week > 0
         then round(100.0 * w.n / w.games_in_week, 1) end as coverage_pct,
    w.games_locked,
    w.games_live,
    w.games_live = 0                                    as is_locked,
    w.excluded_indoor,

    w.mean, w.stddev, w.min_value, w.max_value,
    w.p02, w.p05, w.p25, w.p50, w.p75, w.p95, w.p98,
    w.p75 - w.p25                                       as iqr,
    k.whisker_lo, k.whisker_hi, coalesce(k.outlier_count, 0) as outlier_count,

    -- The histogram's own configuration, carried ON THE ROW so the picture is reproducible
    -- from the row alone and the renderer needs no lookup table.
    e.bin_min, e.bin_max, e.bin_count,
    (e.bin_max - e.bin_min) / e.bin_count               as bin_incr,
    coalesce(t.below_min_count, 0)                      as below_min_count,
    coalesce(t.above_max_count, 0)                      as above_max_count,

    {{ dbt.current_timestamp() }}                       as as_of_ts

from per_week w
join edges e on e.metric = w.metric
left join whiskers k
       on  k.season = w.season and k.season_type = w.season_type
       and k.week = w.week and k.span = w.span
       and k.as_of_date = w.as_of_date and k.metric = w.metric
left join tails t
       on  t.season = w.season and t.season_type = w.season_type
       and t.week = w.week and t.span = w.span
       and t.as_of_date = w.as_of_date and t.metric = w.metric

-- A WEEK NOBODY HAS PRICED YET GETS NO ROW AT ALL. "Won't have data for future weeks until
-- the previous week closes" is a consequence of when books post lines, not a rule to code:
-- n simply comes out zero, and a row of nothing is worse than an Empty state, which the page
-- already knows how to render.
where w.n > 0

{% if is_incremental() %}
  -- Never rewrite a locked week, and never write the same day twice.
  and not exists (
      select 1 from {{ this }} prior
      where prior.season = w.season
        and prior.season_type = w.season_type
        and prior.week = w.week
        and prior.span = w.span
        and prior.metric = w.metric
        and (prior.as_of_date = w.as_of_date or prior.is_locked)
  )
{% endif %}
