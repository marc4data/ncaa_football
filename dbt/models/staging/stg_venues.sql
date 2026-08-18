-- One row per venue. Not season-scoped: /venues takes no year and returns every venue.

with successful_fetches as (

    select
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_venues') }}
    where status_code = 200

),

venues as (

    select {{ json_array_elements('payload') }} as venue
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('venue', 'id') }} as int)   as venue_id,
    {{ json_get_string('venue', 'name') }}              as venue_name,
    {{ json_get_string('venue', 'city') }}              as city,
    {{ json_get_string('venue', 'state') }}             as state,
    {{ json_get_string('venue', 'zip') }}               as zip,
    {{ json_get_string('venue', 'countryCode') }}       as country_code,
    {{ json_get_string('venue', 'timezone') }}          as timezone,
    cast({{ json_get_string('venue', 'latitude') }} as numeric)  as latitude,
    cast({{ json_get_string('venue', 'longitude') }} as numeric) as longitude,
    cast({{ json_get_string('venue', 'elevation') }} as numeric) as elevation_m,
    cast({{ json_get_string('venue', 'capacity') }} as int)      as capacity,
    cast({{ json_get_string('venue', 'constructionYear') }} as int) as construction_year,
    cast({{ json_get_string('venue', 'grass') }} as boolean)     as is_grass,
    cast({{ json_get_string('venue', 'dome') }} as boolean)      as is_dome
from venues
