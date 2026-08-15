-- Reconciliation (data quality rule #4): the mart's team-game count must reconcile to the
-- schedule it was built from, **per season**.
--
-- Every completed game with scores contributes exactly two team-games (one per side), so
-- sum(games_played) must be exactly twice the number of such games in staging. Catches a
-- dropped season, a half-loaded backfill, or a join that fans out.

with from_mart as (

    select season, sum(games_played) as team_games
    from {{ ref('mart_team_season_record') }}
    group by season

),

from_schedule as (

    select season, count(*) * 2 as team_games
    from {{ ref('stg_games') }}
    where is_completed
      and home_points is not null
      and away_points is not null
    group by season

)

select
    coalesce(m.season, s.season) as season,
    m.team_games as mart_team_games,
    s.team_games as schedule_team_games
from from_mart m
full outer join from_schedule s on m.season = s.season
where m.team_games is distinct from s.team_games
