{{ config(materialized='table') }}

-- THE SHAPE OF A WEEK, AT TEAM GRAIN. One row per (season, season_type, week, metric).
--
-- Marc, 2026-09-10, on the offence-against-defence scatterplots: "I'd like to standardize axis
-- across all the FBS matchups for the week… With the accumulated yardage data points, we can
-- calculate averages, min, max, median, and stdev, and percentiles. We use min/max to set axis
-- limits (using logic to give clean breaks and tickmarks), then use the stdev or percentiles to
-- give a visual reference to extreme performers."
--
-- 🚨 A SIBLING OF fct_week_metric_distribution AT A DIFFERENT GRAIN, NOT AN EXTENSION OF IT.
-- That model's metrics are GAME-grain — one spread, one total, one temperature per game. These
-- are TEAM-grain: one figure per team per week. The aggregates are the same family and the
-- membership rule is entirely different, so sharing the model would have meant a `grain` column
-- that half the rows answer differently. Two models, one vocabulary.
--
-- WHY A MODEL AND NOT A HELPER. Eighteen matchup pages in a week must share ONE axis, which
-- means the axis is a property of the WEEK rather than of any page. Computing it in Streamlit
-- means every page pulls 136 team rows to derive the same four numbers, on every rerun.
--
-- ⚠️ THE INPUT IS ALREADY LEAKAGE-SAFE AND THAT IS WHY THIS MODEL IS SHORT. srv_team_week's
-- per-game figures lead INTO the week — Marc's rule, "can only include data through Week 4 in a
-- Week 5 game… That's leakage and unacceptable". This model aggregates them and adds nothing
-- that could reach forward.
--
-- ── THREE DESIGN QUESTIONS, ANSWERED FROM THE DATA ───────────────────────────────────────────
--
-- 1. ⚠️ THERE IS NO `span`, DELIBERATELY. The game-grain model carries week vs season_to_date
--    because a game has ONE value and a reference set has to be assembled from other games.
--    srv_team_week's figures are ALREADY cumulative-to-date, so a `season_to_date` span would
--    aggregate the same numbers under a second name — the same value twice, in a column pair
--    that invites a reader to compare them. Left out rather than shipped inert.
--
-- 2. ⚠️ THERE IS NO `as_of_date` AND NO LOCK RULE, AND THIS IS THE ONE WORTH ARGUING WITH.
--    The game-grain model needs both because its inputs move continuously: a line reprices all
--    week and games kick off across three days, so "as of when" is a real question and a
--    mid-slate row is honestly a mixture. This model's input does not behave that way. Week N's
--    figures are a function of games COMPLETED IN WEEKS STRICTLY BEFORE N, so once week N-1 is
--    final, week N's row is fixed — and by the time anyone is previewing week N, it is.
--    A088's lesson decides the rest: a guard that fires on correct behaviour is worse than
--    none, and an as_of_date history whose rows are all identical is a table that looks like
--    evidence and is not.
--    🚨 THE HONEST EXCEPTION: a postponed game replayed later mutates an earlier week's inputs
--    and this model would silently restate history. It is rebuilt from source every run, so the
--    restatement is correct rather than lost — what is lost is the fact that it happened. That
--    is a real limitation and it is recorded here rather than papered over.
--
-- 3. ⚠️ WEEK 1 PRODUCES NO ROW. Measured: 136 FBS teams carry a week-1 row and ZERO carry a
--    value, because games_counted is 0 for every one of them — the per-game columns are NULL by
--    design, not missing. A distribution over an empty week is not a distribution, so the
--    `having` below emits nothing and the absence reads as an Empty state rather than a row of
--    nulls. Same conclusion the game-grain model reached for its own week 1.

{% set metrics = [
    'total_yards_for_per_game', 'total_yards_allowed_per_game',
    'rushing_yards_for_per_game', 'rushing_yards_allowed_per_game',
    'passing_yards_for_per_game', 'passing_yards_allowed_per_game'
] %}

with long as (

    -- ⚠️ READS THE MART, NOT srv_team_week, AND ci/check_layering.py IS WHY. A mart may depend
    -- on staging or on other marts; `srv_team_week` is SERVING, and the first version of this
    -- model referenced it. The guard failed the build and named the violation exactly — a mart
    -- reaching up into serving is the same bypass as a serving view reaching down past marts,
    -- and the fix was to read the model srv_team_week itself reads.
    --
    -- ⚠️ FBS ONLY. srv_team_week derives `is_fbs` as `classification = 'fbs'` from dim_team;
    -- this is that expression against the same dimension, one layer down. The axis is for FBS
    -- matchups, and a Division II side that appears on one schedule would stretch it for every
    -- page in the week.
    {% for metric in metrics %}
    select y.season, y.season_type, y.week, y.team_id, y.games_counted,
           cast('{{ metric }}' as {{ dbt.type_string() }}) as metric,
           cast(y.{{ metric }} as {{ dbt.type_numeric() }}) as value
    from {{ ref('fct_team_yardage_week') }} y
    join {{ ref('dim_team') }} d
      on d.season = y.season and d.team_id = y.team_id
    where d.classification = 'fbs'
    {{ "union all" if not loop.last }}
    {% endfor %}

),

per_week as (

    select
        season, season_type, week, metric,
        count(value)                                        as n,
        count(*)                                            as teams_in_week,
        min(games_counted)                                  as min_games_counted,
        max(games_counted)                                  as max_games_counted,
        avg(value)                                          as mean,
        stddev_samp(value)                                  as stddev,
        min(value)                                          as min_value,
        max(value)                                          as max_value,
        percentile_cont(0.02) within group (order by value) as p02,
        percentile_cont(0.05) within group (order by value) as p05,
        percentile_cont(0.25) within group (order by value) as p25,
        percentile_cont(0.50) within group (order by value) as p50,
        percentile_cont(0.75) within group (order by value) as p75,
        percentile_cont(0.95) within group (order by value) as p95,
        percentile_cont(0.98) within group (order by value) as p98
    from long
    group by season, season_type, week, metric
    -- See design note 3. No values, no distribution, no row.
    having count(value) > 1

),

spread_stats as (

    -- Tukey, and the same convention the game-grain model states: the whisker reaches the most
    -- extreme OBSERVATION still inside 1.5*IQR, not the fence itself. A fence drawn as a
    -- whisker is longer than the data and reads as a value nobody recorded.
    select p.*,
           p75 - p25                        as iqr,
           p25 - 1.5 * (p75 - p25)          as lower_fence,
           p75 + 1.5 * (p75 - p25)          as upper_fence
    from per_week p

),

whiskers as (

    select s.*,
           (select min(l.value) from long l
             where l.season = s.season and l.season_type = s.season_type
               and l.week = s.week and l.metric = s.metric
               and l.value >= s.lower_fence)                as whisker_low,
           (select max(l.value) from long l
             where l.season = s.season and l.season_type = s.season_type
               and l.week = s.week and l.metric = s.metric
               and l.value <= s.upper_fence)                as whisker_high,
           (select count(*) from long l
             where l.season = s.season and l.season_type = s.season_type
               and l.week = s.week and l.metric = s.metric
               and (l.value < s.lower_fence or l.value > s.upper_fence)) as outlier_count
    from spread_stats s

),

axis as (

    -- 🚨 CLEAN BREAKS, WHICH IS THE HALF OF MARC'S BRIEF A RAW min/max DOES NOT DELIVER.
    -- "We use min/max to set axis limits (using logic to give clean breaks and tickmarks)."
    --
    -- The nice-number rule, and it is the standard's own inversion applied to an axis: aim for
    -- roughly eight intervals, then round the STEP up to the nearest 1 / 2 / 2.5 / 5 / 10 at
    -- the right magnitude and let the tick COUNT fall out. Fixing the step is what makes two
    -- weeks comparable at a glance; fixing the count is what makes every week a different
    -- shape, which is the mistake cfdb_distribution_chart_standard.md §4 already corrected once
    -- for bin width.
    --
    -- ⚠️ THE STEP IS DERIVED, NOT CONFIGURED, AND THAT IS A DEPARTURE WORTH NAMING. The standard
    -- asks for per-metric `bin_width` configuration, and `distribution_bins` in dbt_project.yml
    -- carries entries for the six GAME-grain metrics and none for these. Inventing six more
    -- config entries by eye would be coining numbers; deriving them from the data is honest and
    -- reversible. If Cowork wants them frozen for cross-season comparison, that is a var block
    -- and a one-line change here.
    select w.*,
           {% set raw = "((max_value - min_value) / 8.0)" %}
           case when max_value > min_value then
               {% set mag = "floor(ln(" ~ raw ~ ") / ln(10))" %}
               {% set norm = raw ~ " / power(10, " ~ mag ~ ")" %}
               (case when {{ norm }} <= 1   then 1
                     when {{ norm }} <= 2   then 2
                     when {{ norm }} <= 2.5 then 2.5
                     when {{ norm }} <= 5   then 5
                     else 10 end) * power(10, {{ mag }})
           end                                              as axis_step
    from whiskers w

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'metric']) }} as team_week_distribution_sk,
    season,
    season_type,
    week,
    metric,
    n,
    teams_in_week,
    -- ⚠️ srv_team_week's own header warns that games_counted IS NOT "games played" — it is the
    -- number of completed games cfdb holds BOTH sides' box scores for. Carried so a reader can
    -- see the denominator the week's figures rest on rather than assume it.
    min_games_counted,
    max_games_counted,
    mean,
    stddev,
    min_value,
    max_value,
    p02, p05, p25, p50, p75, p95, p98,
    iqr,
    whisker_low,
    whisker_high,
    outlier_count,
    axis_step,
    -- The limits every matchup in the week shares. Floor and ceiling ONTO the step, so the axis
    -- starts and ends on a labelled tick rather than a fraction of one.
    case when axis_step is not null
         then floor(min_value / axis_step) * axis_step end   as axis_min,
    case when axis_step is not null
         then ceil(max_value / axis_step) * axis_step end    as axis_max
from axis
