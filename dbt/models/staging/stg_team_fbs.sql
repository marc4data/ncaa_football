-- The FBS team list for a season: one row per (season, team), with its venue.
--
-- Same payload shape as /teams, restricted to FBS. Kept as its own model rather than a
-- filter on stg_teams because it is a different endpoint with a different raw table, and
-- because the two do not always agree: /teams is the full universe including FCS opponents
-- and stubs, /teams/fbs is CFBD's own answer to "who is FBS this season". Where they differ,
-- the difference is the interesting part and a filter would hide it.
--
-- `location` IS A FULL VENUE OBJECT, not a city and state. Fourteen fields including capacity,
-- surface, dome and coordinates — the same venue CFBD serves from /venues, embedded. All of
-- it is unnested here; stg_teams read two of the fourteen for years.
--
-- `elevation` ARRIVES AS A STRING ("2024.875732"), unlike every other numeric in the block.
-- safe_numeric absorbs that; a hard cast would work today and break on the first row CFBD
-- sends as an empty string.
--
-- SEASON COMES FROM THE REQUEST, NOT THE ROW. The payload has no year — the season is only
-- in `params`, so an unparameterized fetch describes today rather than any season. Those are
-- excluded, exactly as stg_teams excludes them.

{% set venue_fields = ['name', 'city', 'state', 'zip', 'countryCode', 'timezone',
                       'latitude', 'longitude', 'elevation', 'capacity',
                       'constructionYear'] %}

with season_fetches as (

    select
        filename,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_teams_fbs') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

teams as (

    select season, {{ json_array_elements('payload') }} as team
    from season_fetches
    where recency = 1

)

select
    season,
    cast({{ json_get_string('team', 'id') }} as int)      as team_id,
    {{ json_get_string('team', 'school') }}               as school,
    {{ json_get_string('team', 'mascot') }}               as mascot,
    {{ json_get_string('team', 'abbreviation') }}         as abbreviation,
    {{ json_get_object('team', 'alternateNames') }}       as alternate_names,
    {{ json_get_string('team', 'conference') }}           as conference,
    {{ json_get_string('team', 'division') }}             as division,
    {{ json_get_string('team', 'classification') }}       as classification,
    {{ clean_hex(json_get_string('team', 'color')) }}          as color_raw,
    {{ clean_hex(json_get_string('team', 'alternateColor')) }} as alt_color_raw,
    {{ json_get_object('team', 'logos') }}                as logos,
    {{ json_get_string('team', 'twitter') }}              as twitter,

    cast({{ json_get_nested_string('team', ['location', 'id']) }} as int) as venue_id
{%- for field in venue_fields %},
    {%- if field in ['latitude', 'longitude', 'elevation', 'capacity', 'constructionYear'] %}
    {{ safe_numeric(json_get_nested_string('team', ['location', field])) }}
        as venue_{{ snake_case(field) }}
    {%- else %}
    {{ json_get_nested_string('team', ['location', field]) }}
        as venue_{{ snake_case(field) }}
    {%- endif %}
{%- endfor %},
    cast({{ json_get_nested_string('team', ['location', 'grass']) }} as boolean) as venue_is_grass,
    cast({{ json_get_nested_string('team', ['location', 'dome']) }} as boolean)  as venue_is_dome
from teams
