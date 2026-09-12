{{ config(severity='error') }}
-- R-694. 🚨 THE PAYLOAD HAS NO ATHLETE ID AND THE SOURCE MODEL SAYS SO ITSELF:
-- "Two players with the same name in one game would collide, and there is nothing in the response
-- that could separate them."
--
-- So fct_player_usage_game resolves (game, team, name) to a real player_id through
-- fct_player_game_stat, and drops any name that maps to more than one athlete. ⚠️ THE COLLISION IS
-- NOT THEORETICAL — measured: 4 of 185,427 (game, team, name) keys map to TWO athletes, including
-- Michigan's two Will Johnsons in 2024.
--
-- This asserts the RESULT of that resolution: one row per (game, team, player). A join that fans
-- out shows up here as a duplicated key, and the failing rows NAME the key that collided rather
-- than merely reporting a count.
select
    game_id,
    team_id,
    player_id,
    player_name,
    count(*) as rows_for_this_key,
    'one row per game per team per player' as rule
from {{ ref('fct_player_usage_game') }}
group by game_id, team_id, player_id, player_name
having count(*) > 1
