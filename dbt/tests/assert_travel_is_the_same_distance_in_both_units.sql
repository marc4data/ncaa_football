-- R-634. TWO UNITS, ONE MEASUREMENT — SO THEY MUST RECONCILE.
--
-- The model publishes travel in kilometres and miles, and elevation in metres and feet, because
-- Marc reads miles and feet while CFBD supplies metres. ⚠️ TWO COLUMNS DESCRIBING ONE DISTANCE
-- IS A PAIR THAT CAN DISAGREE, and a wrong conversion factor is invisible in isolation: 1,234
-- miles and 1,986 km both look like plausible numbers on a page.
--
-- So this converts one back into the other and requires them to agree. An international mile is
-- 1.609344 km and an international foot is 0.3048 m, both exact by definition — there is no
-- approximation in the factor, only in the rounding.
--
-- ⚠️ THE TOLERANCE IS THE ROUNDING AND NOTHING MORE. travel_km and travel_miles each carry one
-- decimal, so the worst honest disagreement is 0.05 + 0.05 * 1.609344 = 0.13 km; 0.3 leaves
-- room without leaving room for an error. Feet are whole, so 0.05 + 0.5 * 0.3048 = 0.20 m; 0.35.
-- A factor-of-1000 slip fails by five orders of magnitude, which is the point.
--
-- ALSO ASSERTS THE ABSENCES MATCH. Null means "we do not know where one end was" and 0 means
-- "they played at home" — if one unit is null while the other is not, one of those two meanings
-- has been lost in the conversion.
select game_id, team_id, team,
       travel_km, travel_miles,
       elevation_change_m, elevation_change_ft,
       game_elevation_m, game_elevation_ft,
       home_elevation_m, home_elevation_ft
from {{ ref('fct_game_travel') }}
where abs(travel_km - travel_miles * 1.609344) > 0.3
   or abs(elevation_change_m - elevation_change_ft * 0.3048) > 0.35
   or abs(cast(game_elevation_m as {{ dbt.type_numeric() }}) - game_elevation_ft * 0.3048) > 0.35
   or abs(cast(home_elevation_m as {{ dbt.type_numeric() }}) - home_elevation_ft * 0.3048) > 0.35
   or (travel_km is null) <> (travel_miles is null)
   or (elevation_change_m is null) <> (elevation_change_ft is null)
   or (game_elevation_m is null) <> (game_elevation_ft is null)
   or (home_elevation_m is null) <> (home_elevation_ft is null)
