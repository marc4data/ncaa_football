-- A BYE WEEK CARRIES THE PREVIOUS TOTAL FORWARD RATHER THAN RENDERING ZERO. R-476.
--
-- This is what the calendar spine is FOR. dim_team_week crosses every week in the season with
-- every team in it, and results are LEFT joined on; building from a team's own games instead
-- would produce no row at all for a bye, and a page filtered to that week would render an
-- empty cell rather than the form the team carries into it.
--
-- The failure this catches is subtler than a missing row, and it is the one a coalesce
-- introduces: a bye-week row that EXISTS but reads 0, because the week's own contribution was
-- coalesced to zero and then the running sum was reset rather than carried. Zero yards is a
-- measurement; "the same as last week, because nothing happened" is the truth.
--
-- CHECKED AS AN EQUALITY BETWEEN ADJACENT SLOTS. For any row whose team played nothing in the
-- PREVIOUS slot, this row's cumulative figures must equal the previous row's exactly — same
-- yards, same games_counted. Adjacency is by the season's own chronology, never by week
-- alone.
with slots as (

    select
        y.*,
        lag(y.total_yards_for) over w  as prev_yards,
        lag(y.games_counted)   over w  as prev_games,
        lag(y.week)            over w  as prev_week,
        lag(y.season_type_ordinal) over w as prev_ordinal
    from {{ ref('fct_team_yardage_week') }} y
    window w as (partition by y.season, y.team_id
                 order by y.season_type_ordinal, y.week)

),

-- Did the team actually have a counted game in the PREVIOUS slot? If it did, the totals are
-- supposed to differ and this test says nothing about the row.
played_prev as (

    select s.*,
           coalesce(s.games_counted, 0) - coalesce(s.prev_games, 0) as games_added
    from slots s
    where s.prev_games is not null

)

select season, season_type, week, team_id,
       prev_week, prev_games, games_counted, prev_yards, total_yards_for
from played_prev
-- A slot that added no games is a bye (or an uncounted game): everything must be unchanged.
where games_added = 0
  and (coalesce(total_yards_for, -1) != coalesce(prev_yards, -1)
       or coalesce(games_counted, -1) != coalesce(prev_games, -1))
