-- One row per team **per season**.
--
-- Season scoping is the point. CFBD's /teams accepts a `year`, and the answer differs:
-- for 2024 it reports Boise State in the Mountain West and North Dakota State as FCS,
-- while an unparameterized call reports their *current* affiliations. Joining a
-- season-scoped fact to a current-state dimension produced 2024 rows labelled "Pac-12".
--
-- So: only year-parameterized fetches feed this model. The early unparameterized pulls
-- are deliberately excluded — they describe today, not any particular season.

with season_fetches as (

    select
        filename,
        (params ->> 'year')::int as season,
        content -> 'data'        as payload
    from {{ source('raw', 'raw_teams') }}
    where status_code = 200
      and params ? 'year'

),

latest_per_season as (

    select distinct on (season)
        season,
        payload
    from season_fetches
    order by season, filename desc

),

teams as (

    select
        season,
        jsonb_array_elements(payload) as team
    from latest_per_season

)

select
    season,
    (team ->> 'id')::int             as team_id,
    season::text || '-' || (team ->> 'id') as team_season_key,
    team ->> 'school'                as school,
    team ->> 'mascot'                as mascot,
    team ->> 'abbreviation'          as abbreviation,
    team ->> 'conference'            as conference,
    team ->> 'division'              as division,
    team ->> 'classification'        as classification,
    team -> 'location' ->> 'city'    as city,
    team -> 'location' ->> 'state'   as state
from teams
