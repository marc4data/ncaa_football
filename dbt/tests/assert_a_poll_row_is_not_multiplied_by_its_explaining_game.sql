{{ config(severity='error') }}
-- A190 (cfdb-main-R-1944). srv_rankings holds ONE row per poll, season, week and team.
--
-- WHY THIS TEST EXISTS, AND IT IS NOT HYPOTHETICAL. A190 added a left join from each poll row
-- to the game that explains the move into that week -- poll week N to game week N-1. The first
-- draft of that join carried a comment asserting that fct_game_team is unique on
-- (season, season_type, week, team_id) and therefore could not fan out.
--
-- THAT ASSERTION WAS FALSE. Measured before it shipped: 2,093 duplicate groups exist, for two
-- entirely legitimate reasons --
--
--   postseason      every playoff game carries week = 1, so a finalist has four rows there
--   a double week   Abilene Christian played Lamar AND Texas Tech in 2026 regular week 1
--
-- -- and the exposure reaches real poll rows: 24 in the 2026 FCS Coaches Poll, 2 in the 2023
-- AP Top 25. The join now takes the LAST game of the explaining week by date, so exactly one
-- row can match. This asserts that it stayed that way.
--
-- THE POINT IS THE GRAIN, NOT THE JOIN. Anything else joined onto this view later inherits
-- the same exposure, and a duplicate poll row is not a visible defect: it draws a second dot
-- on the bump chart at the same coordinates and a second identical table row. It looks like
-- nothing. Only a count can see it.
select
    season,
    season_type,
    week,
    poll_name,
    team_id,
    count(*) as rows_at_this_grain
from {{ ref('srv_rankings') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
