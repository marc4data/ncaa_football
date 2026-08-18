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
    {{ json_get_nested_string('team', ['location', 'city']) }}  as city,
    {{ json_get_nested_string('team', ['location', 'state']) }} as state,
    -- Identity chrome. CFBD returns the literal string '#null' for a missing colour, so
    -- these are normalised here and never parsed raw downstream.
    {{ clean_hex(json_get_string('team', 'color')) }}          as color_raw,
    {{ clean_hex(json_get_string('team', 'alternateColor')) }} as alt_color_raw,
    {{ json_get_object('team', 'logos') }}                     as logos
from teams
