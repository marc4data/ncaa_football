-- A BOWL GAME MUST NOT SORT INTO THE MIDDLE OF OCTOBER. R-476.
--
-- Postseason week numbers restart at 1, so a cumulative model ordered on `week` alone would
-- accumulate a January bowl as though it happened in week 1 — before the entire regular
-- season it actually follows. fct_team_yardage_week orders on (season_type_ordinal, week) for
-- exactly this reason, and this asserts the consequence rather than the code.
--
-- THE CONSEQUENCE, STATED AS ARITHMETIC: a team's FIRST postseason slot must carry at least
-- as many counted games as its LAST regular-season slot. If ordering were on week alone, the
-- postseason row would be computed from a window containing little or nothing and would carry
-- FEWER — which is the visible symptom, a bowl matchup showing a team as though it had barely
-- played.
--
-- Restricted to teams that actually reached the postseason and had counted regular-season
-- games, because a team with neither has nothing to compare.
with last_regular as (

    select distinct on (season, team_id)
        season, team_id, week as last_regular_week, games_counted as regular_games
    from {{ ref('fct_team_yardage_week') }}
    where season_type = 'regular'
    order by season, team_id, week desc

),

first_post as (

    select distinct on (season, team_id)
        season, team_id, week as first_post_week, games_counted as post_games
    from {{ ref('fct_team_yardage_week') }}
    where season_type = 'postseason'
    order by season, team_id, week asc

)

select r.season, r.team_id, r.last_regular_week, r.regular_games,
       p.first_post_week, p.post_games
from last_regular r
join first_post p on p.season = r.season and p.team_id = r.team_id
where r.regular_games > 0
  and p.post_games < r.regular_games
