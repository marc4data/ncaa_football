-- One row per team, taken from the most recent *successful* /teams response.
--
-- Two things the raw layer forces us to handle here, not downstream:
--   1. Failed fetches are landed too (a 401 is in the table right now) — filter them
--      out rather than letting nulls leak into the marts.
--   2. Every fetch lands a new file, so the same team appears once per fetch.
--      Take the latest file only; filenames are UTC timestamps, so max() works.

with successful_fetches as (

    select
        filename,
        content -> 'data' as payload
    from {{ source('raw', 'raw_teams') }}
    where status_code = 200

),

latest_fetch as (

    select payload
    from successful_fetches
    where filename = (select max(filename) from successful_fetches)

),

teams as (

    select jsonb_array_elements(payload) as team
    from latest_fetch

)

select
    (team ->> 'id')::int             as team_id,
    team ->> 'school'                as school,
    team ->> 'mascot'                as mascot,
    team ->> 'abbreviation'          as abbreviation,
    team ->> 'conference'            as conference,
    team ->> 'division'              as division,
    team ->> 'classification'        as classification,
    team -> 'location' ->> 'city'    as city,
    team -> 'location' ->> 'state'   as state
from teams
