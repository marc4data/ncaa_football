-- One row per team **per season**.
--
-- Season scoping is the point. CFBD's /teams accepts a `year`, and the answer differs:
-- for 2024 it reports Boise State in the Mountain West and North Dakota State as FCS,
-- while an unparameterized call reports their *current* affiliations. Joining a
-- season-scoped fact to a current-state dimension produced 2024 rows labelled "Pac-12".
--
-- So: only year-parameterized fetches feed this model. The early unparameterized pulls
-- are deliberately excluded — they describe today, not any particular season.
--
-- JSON access goes through the dispatched macros (see macros/json.sql), so this model is
-- dialect-neutral ahead of the Databricks migration.

with season_fetches as (

    select
        filename,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_teams') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

teams as (

    select
        season,
        {{ json_array_elements('payload') }} as team
    from season_fetches
    where recency = 1

)

select
    season,
    cast({{ json_get_string('team', 'id') }} as int)   as team_id,
    cast(season as {{ dbt.type_string() }}) || '-' || {{ json_get_string('team', 'id') }} as team_season_key,
    {{ json_get_string('team', 'school') }}            as school,
    {{ json_get_string('team', 'mascot') }}            as mascot,
    {{ json_get_string('team', 'abbreviation') }}      as abbreviation,
    {{ json_get_string('team', 'conference') }}        as conference,
    {{ json_get_string('team', 'division') }}          as division,
    {{ json_get_string('team', 'classification') }}    as classification,
    -- A JSON ARRAY, carried as JSON. Reading element 0 with the key accessor is how every
    -- logo on the site went missing for weeks; see json_array_element_string in macros/json.
    {{ json_get_object('team', 'alternateNames') }}    as alternate_names,
    {{ json_get_string('team', 'twitter') }}           as twitter,

    -- THE VENUE BLOCK, WHICH THIS MODEL READ TWO FIELDS OF FOR MONTHS.
    --
    -- `location` is not a city and a state. It is a full fourteen-field venue object — the
    -- same venue /venues serves, embedded on every team row — carrying capacity, surface,
    -- dome, coordinates and construction year. The model took `city` and `state` and dropped
    -- the other twelve, which is how /teams sat at 12 of 25 fields in the coverage matrix
    -- while looking complete to anyone reading the model.
    --
    -- Additive: every existing column keeps its name and meaning, so the five models
    -- downstream are unaffected.
    --
    -- `elevation` ARRIVES AS A STRING ("2024.875732") where the other numerics do not.
    -- safe_numeric absorbs that; a hard cast would work today and fail on the first empty
    -- string CFBD sends.
    cast({{ json_get_nested_string('team', ['location', 'id']) }} as int) as venue_id,
    {{ json_get_nested_string('team', ['location', 'name']) }}  as venue_name,
    {{ json_get_nested_string('team', ['location', 'city']) }}  as city,
    {{ json_get_nested_string('team', ['location', 'state']) }} as state,
    {{ json_get_nested_string('team', ['location', 'zip']) }}   as venue_zip,
    {{ json_get_nested_string('team', ['location', 'countryCode']) }} as venue_country_code,
    {{ json_get_nested_string('team', ['location', 'timezone']) }}    as venue_timezone,
    {{ safe_numeric(json_get_nested_string('team', ['location', 'latitude'])) }}
                                                       as venue_latitude,
    {{ safe_numeric(json_get_nested_string('team', ['location', 'longitude'])) }}
                                                       as venue_longitude,
    {{ safe_numeric(json_get_nested_string('team', ['location', 'elevation'])) }}
                                                       as venue_elevation,
    {{ safe_numeric(json_get_nested_string('team', ['location', 'capacity'])) }}
                                                       as venue_capacity,
    {{ safe_numeric(json_get_nested_string('team', ['location', 'constructionYear'])) }}
                                                       as venue_construction_year,
    cast({{ json_get_nested_string('team', ['location', 'grass']) }} as boolean)
                                                       as venue_is_grass,
    cast({{ json_get_nested_string('team', ['location', 'dome']) }} as boolean)
                                                       as venue_is_dome,
    -- Identity chrome. CFBD returns the literal string '#null' for a missing colour, so
    -- these are normalised here and never parsed raw downstream.
    {{ clean_hex(json_get_string('team', 'color')) }}          as color_raw,
    {{ clean_hex(json_get_string('team', 'alternateColor')) }} as alt_color_raw,
    {{ json_get_object('team', 'logos') }}                     as logos
from teams
