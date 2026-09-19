-- A177 (cfdb-main-R-1768). The roster's `has_player_stats` must agree with whether the player
-- actually has a row in `srv_player_stats` for that season.
--
-- 🚨 THE FLAG IS A CACHED ANSWER TO A QUESTION ANOTHER RELATION OWNS, so the only honest test
-- is to ask that relation again and compare. It fires in BOTH directions: a true that resolves
-- to nothing sends a reader to an empty player page, and a false that has stats leaves a
-- working link unmade. Neither is visible on the page as a fault.
--
-- ⚠️ IT WOULD ALSO CATCH THE PERFORMANCE REWRITE GOING WRONG. The flag was built with a
-- correlated EXISTS, which was replaced by a join to a DISTINCT set after the first form ran
-- ten minutes and blocked a live pipeline rebuild. Those two must return the same booleans;
-- this is what says so.
with actual as (
    select distinct season, player_id from {{ ref('srv_player_stats') }}
)
select
    r.season,
    r.player_id,
    r.full_name,
    r.has_player_stats,
    (a.player_id is not null) as really_has_stats
from {{ ref('srv_team_roster') }} r
left join actual a on a.season = r.season and a.player_id = r.player_id
where r.has_player_stats is distinct from (a.player_id is not null)
