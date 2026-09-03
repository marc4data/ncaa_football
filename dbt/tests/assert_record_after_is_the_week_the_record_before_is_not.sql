-- R-140. THE OFF-BY-ONE, STATED AS THE IDENTITY THAT DEFINES IT.
--
-- `current_record` is the record LEADING INTO a week (`rows ... 1 preceding`); `record_after`
-- is the record that week leaves behind (`... current row`). One word apart in the frame, and
-- the whole difference between the two columns.
--
-- So: what a week ENDS with is what the next week STARTS with. Swap the two frames and every
-- row breaks this; point them at the same frame and every row that played breaks it. It can
-- only hold if the two windows differ by exactly one row.
--
-- THE FIRST VERSION OF THIS TEST ASSERTED THE WRONG PREMISE — that a team plays at most one
-- game a week, so each delta had to be 0 or 1. It returned 1,858 rows, and they were real:
-- 823 team-weeks with two wins and 26 with three. Weeks are CFBD's buckets, not a guarantee.
with ordered as (

    select
        season, season_type_ordinal, week, team_id,
        wins, losses, ties, wins_after, losses_after, ties_after,
        lead(wins)   over w as next_wins,
        lead(losses) over w as next_losses,
        lead(ties)   over w as next_ties
    from {{ ref('fct_team_record_week') }}
    window w as (partition by season, team_id order by season_type_ordinal, week)

)
select *
from ordered
where wins_after is not null
  and next_wins is not null
  and (wins_after <> next_wins or losses_after <> next_losses or ties_after <> next_ties)
