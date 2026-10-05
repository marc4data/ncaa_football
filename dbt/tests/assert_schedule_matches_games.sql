{{ config(tags=['scores_refresh_only']) }}
-- 🚨 A283 (cfdb-main-R-4804): THE TAG CHANGED FROM `full_refresh_only` TO `scores_refresh_only`,
-- AND THE PROJECT'S OWN SCOPE CHECKER CHOSE IT, NOT ME.
--
-- While this read `mart_team_schedule` the mart was nobody's ancestor, so NO gated DAG rebuilt
-- both sides — `full_refresh_only` was right. Re-pointed at `srv_team_game_log`:
--
--   cfbd_scores_refresh  `--select +srv_game +srv_team_game_log +srv_week_summary`
--                        rebuilds BOTH sides → it must keep running this
--   cfbd_lines_snapshot  rebuilds `stg_games` and NOT `srv_team_game_log`
--                        → it still straddles there and must stay excluded
--
-- `ci/check_test_refresh_scope.py:230` prints exactly this remedy, and its own comment warns
-- that naming the other tag "sends the next person straight into that refusal, which is what
-- happened to A105". It happened to me too: `full_refresh_only` failed
-- `test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags`, and no tag failed
-- `test_no_test_straddles_the_gated_dags_refresh_boundary`. Two guards, one answer between them.
with per_season as (

    select season, count(*) as team_games
    from {{ ref('srv_team_game_log') }}
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
