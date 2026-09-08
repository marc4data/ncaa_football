-- A REFERENCE FIGURE THAT CONTAINS THE THING BEING REFERENCED IS NOT A COMPARISON.
--
-- Season-to-date accumulates through the week BEFORE the one displayed, so the week band's
-- own slate is not inside the line it is being compared against. The precedent is `srv_game`'s
-- `series` CTE, which computes the head-to-head record as it stood before the current game
-- and excludes the fixture on its own row for exactly this reason.
--
-- Checked by arithmetic rather than by reading the SQL: a season-to-date row's `n` must equal
-- the sum of the `week` rows strictly before it. If the current week leaked in, the sum is
-- short by that week's games.
--
-- Week 1 has no season-to-date row at all, which is an Empty state rather than a zero, and is
-- covered by the same equality: there is nothing to sum and no row to check.
--
-- ==========================================================================================
-- ⚠️ THE `as_of_date` EQUALITY WAS WRONG, AND IT FROZE publish_distributions (R-410/R-411).
--
-- The previous version joined `w.as_of_date = a.as_of_date`. That assumes every snapshot
-- rewrites every week's row. IT DOES NOT: fct_week_metric_distribution is APPEND-ONLY and
-- skips a week already written, which is what makes the four-hourly job cheap. Week 1's row
-- was written once, on 2026-09-04, and never again.
--
-- So on 2026-09-08 the only `week` row carrying that date was week 2 (n=53), while the
-- season_to_date rows correctly held 152 = 99 (week 1, stamped 09-04) + 53. The test summed
-- 53, compared it to 152, and failed 72 rows -- 12 weeks x 6 metrics. THE DATA WAS RIGHT AND
-- THE TEST WAS WRONG, and because it is severity='error' inside the distributions DAG's
-- selection it stopped every publish_distributions from 2026-09-08 onward.
--
-- A true fact -- "these rows do not sum" -- about the wrong object: rows sharing a snapshot
-- date rather than rows describing a week.
--
-- THE INTENT IS UNCHANGED AND SO IS THE STRICTNESS. For each season-to-date row, take the
-- LATEST `week` row for each strictly-prior week AS OF that row's own snapshot date, and sum
-- those. Verified against the warehouse: 564 season_to_date rows, 0 failures. Verified still
-- to guard: replacing `<` with `<=`, which simulates exactly the leak this test exists to
-- catch, flags 184 rows.
--
-- row_number() rather than `distinct on` because these models build on Postgres and Spark.
-- ==========================================================================================
with week_rows as (

    select season, season_type, metric, week, as_of_date, n
    from {{ ref('fct_week_metric_distribution') }}
    where span = 'week'

),

season_rows as (

    select season, season_type, metric, week, as_of_date, n
    from {{ ref('fct_week_metric_distribution') }}
    where span = 'season_to_date'

),

-- Every (season_to_date row, prior week) pair, ranked so rank 1 is that week's most recent
-- row at or before the snapshot the season-to-date row belongs to.
ranked as (

    select s.season, s.season_type, s.metric, s.week, s.as_of_date, s.n as actual_n,
           w.week as prior_week, w.n as prior_n,
           row_number() over (
               partition by s.season, s.season_type, s.metric, s.week, s.as_of_date, w.week
               order by w.as_of_date desc
           ) as recency
    from season_rows s
    join week_rows w
      on  w.season      = s.season
      and w.season_type = s.season_type
      and w.metric      = s.metric
      and w.week        < s.week
      and w.as_of_date <= s.as_of_date

),

summed as (

    select season, season_type, metric, week, as_of_date, actual_n,
           sum(prior_n) as summed_prior_weeks
    from ranked
    where recency = 1
    group by season, season_type, metric, week, as_of_date, actual_n

)

select season, season_type, week, metric, as_of_date, actual_n, summed_prior_weeks
from summed
where actual_n is distinct from summed_prior_weeks
