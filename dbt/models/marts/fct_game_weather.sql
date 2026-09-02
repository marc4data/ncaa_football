{{ config(materialized='table') }}

-- One row per game: conditions at kickoff, joined to the venue's geography.
--
-- 6,847 games across 2024-2026. The endpoint had been landing since August and nothing read
-- it — a field nobody's page needs is invisible from the inside, fetched and stored and never
-- once selected. The Matchup page's Weather section is what it was landed for.
--
-- THIS MODEL IS ALSO THE GAME-TO-VENUE BRIDGE, AND THAT IS ARGUABLY WORTH MORE THAN THE
-- WEATHER.
--
-- srv_game lists travel, rest and elevation as absent because "dim_venue has no join key
-- to fct_game, which carries a venue NAME and no usable venue id". /games/weather carries
-- `venueId` on every row, and it joins to dim_venue for 6,847 of 6,847 — a 100% match. So
-- the missing key was landed all along on an endpoint nobody had read.
--
-- Venue latitude, longitude and elevation are carried here for that reason rather than
-- because a weather panel needs them: they are what a travel or elevation feature has to
-- start from, and putting them on the one model that can supply the key is cheaper than
-- rediscovering the bridge later.
--
-- WEATHER IS REPORTED FOR THE VENUE'S LOCATION, NOT FOR THE PLAYING ENVIRONMENT.
--
-- Domed games carry ordinary outdoor readings: 10.4°F to 98.1°F, 9.3 mph average wind, and
-- five indoor games with measurable precipitation. Rain "inside" a dome is the rain outside
-- it. So `is_indoors` is not a footnote on this model, it is the column that says whether
-- any of the others affected the game, and a page that renders "Rain, 41°F, 12 mph" for a
-- dome without it is stating something false.
--
-- is_indoors agrees with dim_venue.is_dome on every one of the 6,847 rows — two independent
-- sources, zero disagreements — which is worth a test because it is what breaks first if the
-- venue join ever drifts.

with weather as (

    select * from {{ ref('stg_game_weather') }}

),

joined as (

    select
        w.*,
        v.venue_sk,
        v.venue_name        as venue_name_dim,
        v.city,
        v.state,
        v.timezone,
        v.latitude,
        v.longitude,
        v.elevation_m,
        v.capacity,
        v.is_dome,
        v.is_grass
    from weather w
    left join {{ ref('dim_venue') }} v
        on cast(v.venue_id as {{ dbt.type_string() }})
         = cast(w.venue_id as {{ dbt.type_string() }})

)

select
    {{ surrogate_key(['game_id']) }}                      as game_weather_sk,
    game_id,
    season,
    week,
    season_type,
    start_at,

    home_team,
    home_conference,
    away_team,
    away_conference,

    venue_id,
    venue_sk,
    -- The name from the weather payload; venue_name_dim is dim_venue's. Both are kept
    -- because staging deliberately preserves the endpoint's own copy, and a difference
    -- between them is a signal rather than noise.
    venue                                                 as venue,
    venue_name_dim,
    city,
    state,
    timezone,
    latitude,
    longitude,
    elevation_m,
    capacity,
    is_grass,

    -- THE COLUMN THAT QUALIFIES EVERY OTHER ONE. See the header: indoor games still carry
    -- outdoor readings, so this is what says whether they mattered.
    is_indoors,
    is_dome,

    temperature_f,
    dew_point_f,
    humidity_pct,
    precipitation_in,
    snowfall_in,
    pressure_mb,
    wind_speed_mph,
    wind_direction_deg,
    -- A bearing in degrees is not something a reader parses. Eight points is enough to be
    -- useful and coarse enough to stay honest about a single instantaneous reading.
    case when wind_direction_deg is null then null
         else (array['N','NE','E','SE','S','SW','W','NW'])[
                  cast(floor(((cast(wind_direction_deg as numeric) + 22.5) / 45)) as int) % 8 + 1]
    end                                                   as wind_direction_compass,

    weather_condition_code,
    -- Blank on 548 rows, only 6 of them indoors, so this is CFBD omitting the label rather
    -- than a dome having no weather. Normalised to NULL so the page renders an em dash
    -- (AC-G.32) instead of an empty cell that looks like a rendering fault.
    nullif(trim(weather_condition), '')                   as weather_condition,
    -- Precipitation is the fact a reader actually wants from a forecast, and "0.00 in" reads
    -- as a measurement while this reads as an answer. Null-safe: unknown stays unknown.
    case when precipitation_in is null then null
         else precipitation_in > 0 end                    as is_precipitating
from joined
