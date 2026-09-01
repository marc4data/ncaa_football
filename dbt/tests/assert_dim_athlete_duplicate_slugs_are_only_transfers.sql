-- A slug appearing twice in one season must be a transfer, and nothing else.
--
-- athlete_slug is deliberately NOT unique within a season: a player on two rosters in one
-- season is one athlete with two true rows, and the slug follows the athlete rather than the
-- row. Ten such players exist across 2024-2025.
--
-- That makes the honest invariant conditional rather than a uniqueness test — which is why
-- this is a singular test and not `unique` in the yml. A repeated slug is legitimate ONLY
-- when the rows differ by team and agree on the player. Two rows sharing a slug AND a team,
-- or sharing a slug across DIFFERENT players, would both be real defects: the first a
-- genuine duplicate, the second a slug collision the player id was added to prevent.
select season, athlete_slug,
       count(*)                     as rows_for_slug,
       count(distinct team)         as distinct_teams,
       count(distinct player_id)    as distinct_players
from {{ ref('dim_athlete') }}
group by season, athlete_slug
having count(*) <> count(distinct team)
    or count(distinct player_id) <> 1
