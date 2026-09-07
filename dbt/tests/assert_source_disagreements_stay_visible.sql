{{ config(severity='warn') }}
-- The source giving two different answers must stay countable, not disappear into a max() (R-398).
--
-- WARN, NOT ERROR, AND THE REASON MATTERS. This is not a defect we can fix -- CFBD's payload for
-- game 401864424 reports Merrimack's firstDowns as both 7 and 6, and nothing in the payload says
-- which is right. Erroring would put the publish path back exactly where R-398 found it: frozen
-- by data nobody here controls. Warning keeps it on every run's output where it can be watched.
--
-- WHAT IT IS ACTUALLY FOR. The dedupe is deliberately arbitrary, so the risk is not that these
-- rows exist -- it is that they stop being visible and quietly multiply. 44 arbitrary picks in
-- one game is a curiosity. The same query returning 4,400 is a source regression that would
-- otherwise show up only as leaderboards changing for no reason anyone could name.
select 'stg_game_team_stat' as model, game_id, team_id::text as entity,
       stat_category as stat, source_value_count as distinct_values_in_payload
from {{ ref('stg_game_team_stat') }}
where source_value_count > 1

union all

select 'stg_game_player_stat', game_id, athlete_id,
       stat_category || '/' || stat_type, source_value_count
from {{ ref('stg_game_player_stat') }}
where source_value_count > 1
