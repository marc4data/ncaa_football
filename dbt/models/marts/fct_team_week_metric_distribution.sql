{{ config(materialized='table') }}

-- THE SHAPE OF A WEEK, AT TEAM GRAIN. One row per (season, season_type, week, metric).
--
-- Marc, 2026-09-10, on the offense-against-defense scatterplots: "I'd like to standardize axis
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
--
-- 4. 🚨 "WE USE MIN/MAX TO SET AXIS LIMITS" IS THE ONE LINE OF MARC'S BRIEF THIS MODEL NO
--    LONGER FOLLOWS LITERALLY, AND HE IS THE ONE WHO OVERTURNED IT. Built exactly as written,
--    the axis reached 600 on `rushing_yards_for_per_game` because four triple-option academies
--    are in the data every week of every season — and on 2026-09-11, looking at that chart, he
--    said "The charts aren't correct. y-values are 0. That's not correct." The frame is now
--    built over Tukey's whiskers with a floor at zero; min_value and max_value are still
--    published, still describe the week, and no longer decide the scale. See the `frame` CTE
--    for the measurement that settled which basis, and for what it costs.
--
-- 5. ⚠️ THE FRAME IS BUILT OVER 138 FBS TEAMS AND THE PAGE MAY PLOT ANY OF 658 — MEASURED AND
--    DELIBERATELY LEFT THAT WAY (R-641, A097). `srv_team_week` carries 658 teams at 2026
--    regular week 2; 282 of them carry a yardage value, being the FBS sides plus every
--    non-FBS opponent an FBS school scheduled. Widening this model to all 282 was costed:
--    on a whisker basis it would TIGHTEN most frames, so the argument against it is not the
--    axis at all — it is p25/p50/p75, which the page draws as "the middle half of the week".
--    Including non-FBS opponents moves the median by up to 61.5 yards, and in OPPOSITE
--    directions for `_for` and `_allowed` metrics, because those sides gain less and concede
--    more. That changes what the reader is being compared against, which is a question about
--    what the site should say rather than about how the axis is computed — Marc's call, not
--    this model's. The FBS spine stays (R-051), and `_off_the_frame` in the page names the
--    handful of teams the frame excludes.

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

    -- 🚨 ONE GROUPED PASS, NOT THREE CORRELATED SUBQUERIES PER ROW — AND A097 MEASURED WHY IT
    -- HAD TO CHANGE. The three subqueries below used to be correlated against `long`, which was
    -- affordable only while their results were referenced twice in the final select. R-641 moved
    -- the axis onto `whisker_high`/`whisker_low`, and the nice-number rule expands its input
    -- expression about ten times over (`raw` appears inside `mag`, `mag` inside `norm`, `norm`
    -- in four case branches, then `axis_step` again in axis_min and axis_max). Postgres inlines
    -- a CTE referenced once, so each of those copies became another execution of the correlated
    -- scan.
    --
    -- ⚠️ MEASURED, NOT REASONED: on 2026 alone, axis-over-extremes ran in 0.9s and
    -- axis-over-whiskers in 65.5s — the SAME correlated subqueries, seventy times the work,
    -- purely from where their output was referenced. The full build had passed 28 minutes and
    -- was still going.
    --
    -- This form computes each week's whiskers ONCE, grouped, and joins them. It is also why
    -- `long` and `spread_stats` are each referenced twice now: a CTE referenced more than once
    -- is materialised rather than inlined, so the expensive scans happen a single time.
    -- ⚠️ THE SEMANTICS ARE UNCHANGED — min/max of the values inside the fence, count of those
    -- outside — and A097 verified that every whisker_low, whisker_high and outlier_count in all
    -- 282 rows is byte-identical to what the correlated form produced.
    select s.*,
           b.whisker_low,
           b.whisker_high,
           coalesce(b.outlier_count, 0)                     as outlier_count
    from spread_stats s
    left join (
        select l.season, l.season_type, l.week, l.metric,
               -- Tukey: the whisker reaches the most extreme OBSERVATION still inside the
               -- fence, never the fence itself. A fence drawn as a whisker is longer than the
               -- data and reads as a value nobody recorded.
               min(case when l.value >= f.lower_fence then l.value end) as whisker_low,
               max(case when l.value <= f.upper_fence then l.value end) as whisker_high,
               sum(case when l.value < f.lower_fence
                         or l.value > f.upper_fence then 1 else 0 end)  as outlier_count
        from long l
        join spread_stats f
          on f.season = l.season and f.season_type = l.season_type
         and f.week = l.week and f.metric = l.metric
        group by l.season, l.season_type, l.week, l.metric
    ) b
      on b.season = s.season and b.season_type = s.season_type
     and b.week = s.week and b.metric = s.metric

),

frame as (

    -- 🚨 THE FRAME IS BUILT OVER THE BODY OF THE WEEK, NOT OVER ITS EXTREMES. R-641/R-642.
    --
    -- Marc, 2026-09-11, looking at a rushing chart: "The charts aren't correct. y-values are 0.
    -- That's not correct." ⚠️ HE WAS RIGHT AND THE NUMBER WAS RIGHT AT THE SAME TIME. B086
    -- measured what he was actually seeing: Michigan's 106.0 drawn "a point 26 pixels off the
    -- floor of a 150-pixel chart, because the rushing axis runs to 600 while three quarters of
    -- the league sits below 240."
    --
    -- MEASURED AT 2026 REGULAR WEEK 2, on the axis this model used to build:
    --
    --   rushing_yards_for_per_game   axis [0, 600]   whisker [2, 365]   max 569   4 outliers
    --   103 of the 282 teams carrying a value — 36.5% — sat in the BOTTOM FIFTH of the frame.
    --
    -- ⚠️ THE FOUR OUTLIERS ARE Army 569, Navy 506, Rice 465, Air Force 431. Triple-option
    -- offenses are a structural feature of the sport, not noise: they are there every week of
    -- every season, and on a min/max axis they stretch the frame for all 138 teams. An axis
    -- built over them is an axis built for four teams and against the other 134.
    --
    -- ── WHY TUKEY'S WHISKER AND NOT A FIXED PERCENTILE ──────────────────────────────────────
    --
    -- p05/p95 and p02/p98 are both on this row and were both measured before choosing. The
    -- deciding property is what each does to a metric that has NOTHING to trim. Counting
    -- team-metric observations pushed outside their own frame at 2026 regular week 2:
    --
    --   whisker + floor at 0      15 off-frame,  0 on metrics with no outliers
    --   p02 / p98                 20 off-frame,  2 on metrics with no outliers
    --   p05 / p95                 74 off-frame, 17 on metrics with no outliers
    --
    -- 🚨 A FIXED QUANTILE ALWAYS EXCLUDES A FIXED FRACTION, WHETHER OR NOT ANYTHING IS
    -- DETACHED FROM THE BODY. `passing_yards_for_per_game` and `total_yards_for_per_game` have
    -- outlier_count = 0 at this week — no straggler, nothing to tighten — and a p95 frame still
    -- throws teams off them to solve a problem they do not have. Tukey's whisker IS an
    -- observation, so when there are no outliers whisker_high = max_value and the frame comes
    -- out UNCHANGED. It tightens exactly where there is something to tighten and nowhere else.
    --
    -- That is also why `outlier_count` is already published: the cost of this frame is stated
    -- per row rather than assumed.
    --
    -- ── R-642: THE FLOOR IS ZERO, AND IT IS THE AXIS THAT IS CLAMPED, NEVER THE VALUE ───────
    --
    -- `rushing_yards_allowed_per_game` carried axis_min = -50 on 14 rows, because min_value is
    -- -7.0 — SACKS COUNT AGAINST RUSHING, so a team that has played one game can genuinely
    -- concede a negative rushing average. ⚠️ THE -7.0 IS REAL DATA AND IT SURVIVES UNTOUCHED
    -- in fct_team_yardage_week and srv_team_week. What was wrong was spending an eighth of
    -- every matchup's frame on territory one team occupies.
    --
    -- B084 reached the same conclusion from the other end a week ago, about the band rather
    -- than the axis: a ±1σ band at week 2 "extends below zero, which is not a yardage." Same
    -- conclusion, second route, so it is not a matter of taste.
    --
    -- ⚠️ ALL SIX METRICS IN THIS MODEL ARE YARDS PER GAME, which is why the floor can be a flat
    -- zero rather than a per-metric setting. A signed metric added to the list above would need
    -- this revisited, and assert_a_yardage_axis_never_starts_below_zero.sql is what makes that
    -- a failing build rather than a silent sign error.
    --
    -- ⚠️ A TIGHTER FRAME PUTS SOME TEAMS OUTSIDE IT, AND THAT IS ONLY SHIPPABLE BECAUSE B086
    -- BUILT THE OTHER HALF. `_off_the_frame` refuses the chart, names the metric, and the two
    -- figures are printed as text one line above — so an excluded team loses a misleading
    -- picture and no measurement. A week before B086 this change would have drawn the point
    -- floating in the margin past the last tick, which is a worse defect than the squash.
    select w.*,
           -- The ends of the frame BEFORE the step rounds them onto a labelled tick.
           greatest(cast(0 as {{ dbt.type_numeric() }}), whisker_low) as frame_low,
           whisker_high                                              as frame_high
    from whiskers w

),

axis as (

    -- 🚨 CLEAN BREAKS, WHICH IS THE HALF OF MARC'S BRIEF A RAW RANGE DOES NOT DELIVER.
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
    --
    -- ⚠️ THE STEP IS DERIVED FROM THE FRAME THAT IS ACTUALLY DRAWN, which is why it moved with
    -- the limits rather than staying on min/max. A step derived from a range nobody draws puts
    -- the tick labels at a spacing chosen for a different chart: at 2026 regular week 2
    -- `rushing_yards_for_per_game` went [0, 600] step 100 → [0, 400] step 50, so the reader
    -- gets eight labelled ticks over the body of the league instead of six over its tail.
    select f.*,
           {% set raw = "((frame_high - frame_low) / 8.0)" %}
           case when frame_high > frame_low then
               {% set mag = "floor(ln(" ~ raw ~ ") / ln(10))" %}
               {% set norm = raw ~ " / power(10, " ~ mag ~ ")" %}
               (case when {{ norm }} <= 1   then 1
                     when {{ norm }} <= 2   then 2
                     when {{ norm }} <= 2.5 then 2.5
                     when {{ norm }} <= 5   then 5
                     else 10 end) * power(10, {{ mag }})
           end                                              as axis_step
    from frame f

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
    --
    -- 🚨 OVER frame_low / frame_high — THE WHISKERS, FLOORED AT ZERO — NOT min_value / max_value.
    -- See the `frame` CTE above for why, what it cost to measure, and what it excludes. The
    -- invariant this leaves behind is exact and tested: axis_max lands in
    -- [whisker_high, whisker_high + axis_step) and axis_min in (frame_low - axis_step, frame_low].
    case when axis_step is not null
         then floor(frame_low / axis_step) * axis_step end   as axis_min,
    case when axis_step is not null
         then ceil(frame_high / axis_step) * axis_step end   as axis_max
from axis
