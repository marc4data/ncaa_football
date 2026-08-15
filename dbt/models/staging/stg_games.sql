-- One row per game, across every season landed in raw.
--
-- Dedup is keyed on the **whole params object**, not on the season alone. The backfill
-- fetches each season twice — once for `seasonType=regular`, once for `postseason` — so
-- deduping per season would silently discard the bowl games. Keying on params generalises:
-- one surviving file per distinct request, whatever dimensions that request had.

with successful_fetches as (

    select
        filename,
        params,
        content -> 'data' as payload
    from {{ source('raw', 'raw_games') }}
    where status_code = 200

),

latest_per_request as (

    select distinct on (params)
        params,
        payload
    from successful_fetches
    order by params, filename desc

),

games as (

    select jsonb_array_elements(payload) as game
    from latest_per_request

)

select
    (game ->> 'id')::int                 as game_id,
    (game ->> 'season')::int             as season,
    (game ->> 'week')::int               as week,
    game ->> 'seasonType'                as season_type,
    (game ->> 'startDate')::timestamptz  as start_date,
    (game ->> 'completed')::boolean      as is_completed,
    (game ->> 'conferenceGame')::boolean as is_conference_game,
    (game ->> 'neutralSite')::boolean    as is_neutral_site,
    (game ->> 'homeId')::int             as home_team_id,
    game ->> 'homeTeam'                  as home_team,
    (game ->> 'homePoints')::int         as home_points,
    game ->> 'homeClassification'        as home_classification,
    (game ->> 'awayId')::int             as away_team_id,
    game ->> 'awayTeam'                  as away_team,
    (game ->> 'awayPoints')::int         as away_points,
    game ->> 'awayClassification'        as away_classification,
    game ->> 'venue'                     as venue,
    (game ->> 'attendance')::int         as attendance
from games
