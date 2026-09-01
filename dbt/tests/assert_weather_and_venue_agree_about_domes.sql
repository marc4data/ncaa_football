-- Two independent sources say whether a game was indoors, and they must not disagree.
--
-- /games/weather ships `is_indoors` per game; dim_venue carries `is_dome` per venue, built
-- from a different endpoint. They agree on all 6,847 rows today — 6,694 outdoor, 153 indoor,
-- zero disagreements.
--
-- This is a join test wearing a data-quality hat. fct_game_weather joins weather to dim_venue
-- on venue_id, and that join is the bridge srv_matchup needs for travel and elevation. If it
-- ever drifts — a reused venue id, a renumbering, a cast changing behaviour between engines —
-- the first visible symptom is a domed stadium claiming to be open air, and every geography
-- column on the row would be wrong in the same silent way.
--
-- Rows with no dim_venue match are excluded rather than failed: the match is 100% today, and
-- a genuinely new venue arriving before the dimension is refreshed is a coverage gap, not a
-- contradiction. assert_weather_rows_all_resolve_to_a_venue would be the test for that, and
-- it does not exist because a 100% join is not yet a promise anyone has made.
select game_id, venue_id, venue, is_indoors, is_dome
from {{ ref('fct_game_weather') }}
where is_dome is not null
  and is_indoors is distinct from is_dome
