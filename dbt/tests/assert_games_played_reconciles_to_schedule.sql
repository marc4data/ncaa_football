{{ config(tags=['scores_refresh_only']) }}
-- 🚨 A283 (cfdb-main-R-4804): `full_refresh_only` -> `scores_refresh_only`, named by
-- `ci/check_test_refresh_scope.py` rather than chosen by me:
--
--   "assert_games_played_reconciles_to_schedule straddles cfbd_lines_snapshot's refresh
--    boundary: it reads [stg_games], which cfbd_lines_snapshot rebuilds, against
--    [srv_standings], which it does not. Tag it `scores_refresh_only` — cfbd_scores_refresh
--    rebuilds both sides and must keep running it"
--
-- While this read `mart_team_season_record` no gated DAG rebuilt both sides, so the blunt tag
-- was right. Re-pointed at `srv_standings`, one of them does — and removing it from that DAG
-- too would be coverage given away.
with from_mart as (

    select season, sum(games_played) as team_games
    from {{ ref('srv_standings') }}
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
