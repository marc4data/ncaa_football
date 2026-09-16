{{ config(materialized='table') }}

-- THE SHAPE OF THE SEASON SO FAR, AT SINGLE-GAME TEAM GRAIN. A143, cfdb-main-R-973.
-- One row per (season, season_type, week, metric): every team-game played in weeks STRICTLY
-- BEFORE this one.
--
-- 🚨 A FOURTH SIBLING, AND THE PROJECT HAS NOW REFUSED TO MERGE THESE THREE TIMES. Two things
-- distinguish this family and only one of them used to vary, which is why the name grew a suffix:
--
--     model                                       GRAIN                 WINDOW
--     fct_week_metric_distribution                game (one fixture)    the week
--     fct_team_week_metric_distribution           team                  cumulative, AVERAGES
--     fct_game_team_metric_distribution           team, single game     the week
--     THIS MODEL                                  team, single game     cumulative, OBSERVATIONS
--
-- ⚠️ §4.3 — THE NAME CARRIES THE WINDOW, AND THE SUFFIX IS NOT INVENTED. `_through_prior_week` is
-- already this project's word for exactly this point-in-time meaning: `fct_player_leader_week`
-- publishes `yards_through_prior_week`, and `srv_game_team_leader_through_prior_week` is in the
-- serving registry. Picking from the vocabulary rather than coining `_v2` or `_to_date` is the
-- whole of §4.3, and `_to_date` was rejected because it does not say which side of the current
-- week it falls on — which is the one thing a reader of this model must not have to guess.
--
-- ── WHY IT EXISTS: THE OBJECT B118 WAS TOLD TO READ CANNOT SERVE A PREVIEW ───────────────────
--
-- 🚨 `fct_game_team_metric_distribution` RETURNS NO ROW FOR A WEEK NOBODY HAS PLAYED YET, and that
-- is structural rather than a data gap — its own header says "a single-game observation belongs to
-- the week it was PLAYED in", and it carries no `span`. 📊 MEASURED on live serving: for 2026 it
-- serves regular weeks 1 and 2 and nothing else, while **2,924 regular-season games are unplayed**.
-- A week-3 preview asks it for a distribution and gets zero rows.
--
-- 🚨 AND THE FAILURE WOULD HAVE BEEN SILENT. `box(None)` returns a titled em dash rather than
-- raising, so all six charts on every upcoming matchup would have gone blank with every
-- "the chart element is present" assertion still passing. B118 found it before building on it.
--
-- ── WHY NOT THE AVERAGES MODEL, WHICH *DOES* SERVE EVERY WEEK ────────────────────────────────
--
-- 🚨 BECAUSE IT DESCRIBES A DIFFERENT POPULATION FROM THE MARKS DRAWN ON IT. Marc asked for "an
-- unfilled circle mark indicating the measure for each game the team played" — SINGLE GAMES —
-- against a box built from SEASON AVERAGES. Averaging shrinks variance, so the box is far too
-- narrow for the points inside it.
--
-- 📊 MEASURED, every team-game in the closed pool for 2026 regular weeks < 3 (n = 370), against
-- the box a week-3 preview would draw:
--
--     box                                     p25      p75   IQR width   beyond a whisker   outside the middle half
--     averages (what shipped)             346.475  461.375       114.9            18.92%                    71.89%
--     cumulative game grain (this model)    255.5    474.8       219.3             0.27%                    50.27%
--
-- ⚠️ A CORRECTLY FRAMED BOX PUTS ~50% OF ITS POPULATION OUTSIDE ITS MIDDLE HALF, BY DEFINITION.
-- This model lands at 50.27%; the averages box lands at 71.89% and its middle half is 47.6%
-- narrower than it should be. And the tail claim is the one a reader would actually misread: the
-- averages box says roughly one afternoon in five was extraordinary when the truth is one in 370.
--
-- ⚠️ B118 MEASURED THE SAME THING FIRST AND THIS ROUND REPRODUCED IT rather than taking its word
-- (§2.4): 15.42% against 0.30%, and 70.4% against 48.1%. Same direction, same order of magnitude,
-- different denominators — B118 used all 668 played team-games, this used the 370 the box actually
-- describes.
--
-- ── THE LEAKAGE RULE, AND A DEPARTURE FROM THE PRECEDENT THAT IS FORCED RATHER THAN CHOSEN ───
--
-- 🚨 STRICTLY BEFORE W. A week-W row that included week W's own games would be leakage, and this
-- object is read BEFORE KICKOFF — the same line `fct_player_leader_week` and `fct_team_record_week`
-- draw. Marc's rule: "Can only include data through Week 4 in a Week 5 game… That's leakage and
-- unacceptable." R-463.
--
-- ⚠️ `fct_player_leader_week` ENFORCES IT IN A WINDOW FRAME AND SAYS WHY: "a leakage rule enforced
-- by a filter is a rule one careless join removes… Delete any line you like and the leakage rule
-- survives, because it lives in the frame." **THAT SHAPE IS NOT AVAILABLE HERE, AND THE DATABASE
-- SAYS SO RATHER THAN ME:**
--
--     OVER is not supported for ordered-set aggregate percentile_cont
--
-- A percentile cannot be accumulated over a window frame in Postgres, so the window has to be a
-- JOIN PREDICATE — which is exactly the "one careless join" shape that header warns about.
-- ✅ SO THE COMPENSATING CONTROL IS A TEST RATHER THAN A COMMENT:
-- `assert_the_prior_week_distribution_excludes_its_own_week` recomputes the boundary independently
-- and fires if it moves by a single week. The precedent gets its guarantee from the frame; this
-- model has to earn the same guarantee from an assertion, and saying so is the point of this note.
--
-- ⚠️ ORDERED BY (season_type_ordinal, week), NEVER BY week ALONE — `fct_team_yardage_week`'s rule:
-- "Postseason week numbers restart at 1, so ordering on week would sort a bowl game into the
-- middle of October." ✅ It also means a POSTSEASON week 1 preview inherits the whole regular
-- season, which is the answer a bowl-game reader wants; partitioning inside season_type would hand
-- them an empty box in the one week they care most about.
--
-- ⚠️ WALK THE CALENDAR, NOT THE GAMES — and it is the trap this model exists to avoid, so building
-- the spine from played games would reproduce the exact defect in a new object. `dim_team_week` is
-- the SHARED spine and carries `season_type_ordinal` already; a second spine that drifts from the
-- first is this project's signature defect.
--
-- ✅ WEEK 1 PRODUCES NO ROW, under this relation and under the single-week sibling both, and for
-- the honest reason: there is nothing before it. The page's existing empty-state wording is still
-- true of this object.
--
-- ⚠️ NO SEPARATE DENOMINATOR COLUMN, AND THAT IS A DEPARTURE WORTH NAMING. The siblings publish
-- `teams_in_week` / `team_games_in_week` beside `n` because their populations can carry a row with
-- no value. Here the window is built from OBSERVATIONS — `value is not null` is applied before the
-- join — so `n` IS the number of team-games the box is drawn from, and a second column equal to it
-- would be the same number twice under two names. `weeks_counted` carries the fact that actually
-- travels with the numerator (AC-G.33): how many weeks of football this is over.
--
-- ⚠️ THE NULL FILTER IS ALSO WHAT KEEPS THE NON-EQUI JOIN PROPORTIONAL TO THE DATA. The source
-- spans 157 seasons and 2,183 week-slots, of which only 36 carry any value at all — box scores and
-- advanced stats are 2024+. Joining the other 2,147 slots would multiply ~2.9M valueless rows by
-- their seasons' week counts to produce nothing.

with spine as (

    -- Every week a PREVIEW can be drawn for, from the shared calendar spine.
    select distinct season, season_type, season_type_ordinal, week
    from {{ ref('dim_team_week') }}

),

long as (

    -- ⚠️ THE ORDINAL COMES FROM THE SPINE RATHER THAN FROM A SECOND COPY OF THE LIST.
    -- `dim_team_week` already maps season_type to its ordinal; restating
    -- ('regular', 1), ('postseason', 2), … here is the drift this project keeps paying for.
    select
        v.season, v.season_type, v.week, v.metric, v.value,
        s.season_type_ordinal
    from {{ ref('int_game_team_metric_value') }} v
    join spine s
      on  s.season      = v.season
      and s.season_type = v.season_type
      and s.week        = v.week
    where v.value is not null

),

observed as (

    -- 🚨 THE LEAKAGE BOUNDARY, AND IT IS THIS ONE LINE. `<`, never `<=`.
    -- The row comparison orders by season type first, so a postseason week 1 sees the whole
    -- regular season and a regular week 1 sees nothing.
    select
        s.season, s.season_type, s.week,
        l.metric, l.value, l.week as played_week
    from spine s
    join long l
      on  l.season = s.season
      and (l.season_type_ordinal, l.week) < (s.season_type_ordinal, s.week)

),

per_week as (

    select
        season, season_type, week, metric,
        count(value)                                        as n,
        count(distinct played_week)                         as weeks_counted,
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
    from observed
    group by season, season_type, week, metric
    -- One observation is not a distribution. No row rather than a box with no width — the rule
    -- all three siblings state, in their words.
    having count(value) > 1

),

spread_stats as (

    select p.*,
           p75 - p25                        as iqr,
           p25 - 1.5 * (p75 - p25)          as lower_fence,
           p75 + 1.5 * (p75 - p25)          as upper_fence
    from per_week p

),

whiskers as (

    -- 🚨 ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW. A097 measured the other shape on
    -- this exact family at 0.9s against 65.5s — the same subqueries, seventy times the work,
    -- purely from where their output was referenced. The siblings carry the full post-mortem.
    select s.*,
           b.whisker_low,
           b.whisker_high,
           coalesce(b.outlier_count, 0)                     as outlier_count
    from spread_stats s
    left join (
        select o.season, o.season_type, o.week, o.metric,
               -- Tukey, and the convention all three siblings state: the whisker reaches the most
               -- extreme OBSERVATION still inside 1.5*IQR, never the fence itself. A fence drawn
               -- as a whisker is longer than the data and reads as a value nobody recorded.
               min(case when o.value >= f.lower_fence then o.value end) as whisker_low,
               max(case when o.value <= f.upper_fence then o.value end) as whisker_high,
               sum(case when o.value < f.lower_fence
                         or o.value > f.upper_fence then 1 else 0 end)  as outlier_count
        from observed o
        join spread_stats f
          on  f.season = o.season and f.season_type = o.season_type
         and f.week = o.week and f.metric = o.metric
        group by o.season, o.season_type, o.week, o.metric
    ) b
      on  b.season = s.season and b.season_type = s.season_type
     and b.week = s.week and b.metric = s.metric

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'metric']) }}
        as game_team_metric_distribution_through_prior_week_sk,
    season,
    season_type,
    week,
    metric,
    n,
    weeks_counted,
    -- ⚠️ PUBLISHED UNROUNDED, MATCHING ALL THREE SIBLINGS. `percentile_cont` returns double
    -- precision and none of them rounds; the page formats. Rounding here would make this the one
    -- model of four with a different convention, which is how one vocabulary becomes two.
    mean,
    stddev,
    min_value,
    max_value,
    p02, p05, p25, p50, p75, p95, p98,
    iqr,
    whisker_low,
    whisker_high,
    outlier_count
from whiskers
