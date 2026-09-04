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
with expected as (
    select a.season, a.season_type, a.week, a.metric, a.as_of_date, a.n as actual_n,
           (select sum(w.n)
              from {{ ref('fct_week_metric_distribution') }} w
             where w.season = a.season
               and w.season_type = a.season_type
               and w.span = 'week'
               and w.metric = a.metric
               and w.as_of_date = a.as_of_date
               and w.week < a.week) as summed_prior_weeks
    from {{ ref('fct_week_metric_distribution') }} a
    where a.span = 'season_to_date'
)
select * from expected
where actual_n is distinct from summed_prior_weeks
