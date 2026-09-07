{{ config(severity='warn') }}
-- The source giving two different answers must stay countable, not disappear into a max() (R-398).
--
-- WARN, NOT ERROR. This is not a defect we can fix: CFBD reports Merrimack's firstDowns as both
-- 7 and 6 for game 401864424, and nothing in the payload says which is right. Erroring would put
-- the publish path back exactly where R-398 found it -- frozen by data nobody here controls.
--
-- The dedupe is deliberately arbitrary, so the risk is not that these rows exist; it is that they
-- stop being visible and quietly multiply. 44 arbitrary picks in one game is a curiosity. The same
-- query returning 4,400 is a source regression that would otherwise surface only as leaderboards
-- changing for no reason anyone could name.
--
-- ⚠️ ONE MODEL PER TEST, AND CI IS WHY. The first draft queried both staging models in one union.
-- ci/check_test_refresh_scope.py rejected it: stg_game_team_stat is rebuilt by cfbd_scores_refresh
-- and stg_game_player_stat is not, so the test straddled the refresh boundary and would have
-- blocked publish_to_serving whenever the two sides sat at different refreshes -- re-creating the
-- exact outage this commit repairs. Split so neither test spans the boundary.
select game_id, team_id, stat_category, source_value_count as distinct_values_in_payload
from {{ ref('stg_game_team_stat') }}
where source_value_count > 1
