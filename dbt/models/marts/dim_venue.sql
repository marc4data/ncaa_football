{{ config(materialized='table') }}

-- One row per venue. Not season-scoped: stadiums outlive seasons.
--
-- NOTE: /games carries the venue NAME, not a venue id, so joining this to fct_game is
-- name-based and lossy. fct_game therefore keeps the venue name denormalized and does not
-- carry a venue_sk. This dimension stands on its own for venue attributes (capacity, dome,
-- elevation) until a reliable join key exists.

select
    {{ surrogate_key(['venue_id']) }} as venue_sk,
    venue_id,
    venue_name,
    city,
    state,
    zip,
    country_code,
    timezone,
    latitude,
    longitude,
    elevation_m,
    capacity,
    construction_year,
    is_grass,
    is_dome
from {{ ref('stg_venues') }}
