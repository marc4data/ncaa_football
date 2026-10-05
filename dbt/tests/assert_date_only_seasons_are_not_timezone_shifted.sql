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
select
    s.season,
    s.game_id,
    s.game_date,
    g.start_date
from {{ ref('srv_team_game_log') }} s
join {{ ref('stg_games') }} g on g.game_id = s.game_id
where not s.kickoff_time_known
  and s.game_date <> {{ to_utc_date('g.start_date') }}
