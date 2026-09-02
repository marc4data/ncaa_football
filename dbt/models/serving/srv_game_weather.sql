-- Matchup page, Weather section: one row per game with conditions and venue geography.
--
-- A SEPARATE VIEW RATHER THAN COLUMNS ON srv_game, deliberately. srv_game is already
-- the widest object in the model at 77 columns and 110,879 rows, and weather exists for
-- 6,847 of those games — 2024 onward only. Widening it would add twenty-odd columns that are
-- null on 94% of rows and grow the largest serving table to carry them.
--
-- The site reads one relation per query, not one relation per page, so a section querying
-- its own view is the pattern rather than the exception.
--
-- WEATHER DESCRIBES THE VENUE'S LOCATION, NOT THE PLAYING ENVIRONMENT. Domed games carry
-- ordinary outdoor readings — including five with measurable precipitation — so `is_indoors`
-- is what says whether any of it reached the field. A page rendering conditions without it
-- is stating something false.
select
    w.game_weather_sk,
    w.game_id,
    w.season,
    w.week,
    w.season_type,
    w.start_at,
    w.home_team,
    w.away_team,
    w.venue,
    w.city,
    w.state,
    w.timezone,
    w.latitude,
    w.longitude,
    w.elevation_m,
    w.capacity,
    w.is_grass,
    w.is_indoors,
    w.temperature_f,
    w.dew_point_f,
    w.humidity_pct,
    w.precipitation_in,
    w.snowfall_in,
    w.pressure_mb,
    w.wind_speed_mph,
    w.wind_direction_deg,
    w.wind_direction_compass,
    w.weather_condition,
    w.is_precipitating,
    ao.as_of_ts
from {{ ref('fct_game_weather') }} w
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
