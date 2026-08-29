{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only`: excluded from cfbd_scores_refresh, which rebuilds one side of
-- this comparison and not the other. Full authority on the weekly +tag:production
-- build, which rebuilds both. See dags/scores_refresh_dag.py TEST_EXCLUDE.
-- Reconciliation (rule #4): the schedule mart must account for every game exactly twice —
-- once from each side. Catches a dropped side of the union, a fan-out in the team join,
-- and any season that silently failed to land.

with per_season as (

    select season, count(*) as team_games
    from {{ ref('mart_team_schedule') }}
    group by season

),

from_games as (

    select season, count(*) * 2 as team_games
    from {{ ref('stg_games') }}
    group by season

)

select
    coalesce(s.season, g.season) as season,
    s.team_games as schedule_team_games,
    g.team_games as expected_team_games
from per_season s
full outer join from_games g on s.season = g.season
where s.team_games is distinct from g.team_games
