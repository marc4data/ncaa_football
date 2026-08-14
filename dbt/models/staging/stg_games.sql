-- One row per game, from the most recent successful /games response *per season*.
--
-- Unlike teams, games are fetched per-season, so "latest file" has to be scoped to
-- the season in the request params — otherwise refetching 2025 would hide 2024.

with successful_fetches as (

    select
        filename,
        params ->> 'year' as fetched_year,
        content -> 'data' as payload
    from {{ source('raw', 'raw_games') }}
    where status_code = 200

),

latest_per_season as (

    select distinct on (fetched_year)
        fetched_year,
        payload
    from successful_fetches
    order by fetched_year, filename desc

),

games as (

    select jsonb_array_elements(payload) as game
    from latest_per_season

)

select
    (game ->> 'id')::int              as game_id,
    (game ->> 'season')::int          as season,
    (game ->> 'week')::int            as week,
    game ->> 'seasonType'             as season_type,
    (game ->> 'startDate')::timestamptz as start_date,
    (game ->> 'completed')::boolean   as is_completed,
    (game ->> 'conferenceGame')::boolean as is_conference_game,
    (game ->> 'neutralSite')::boolean as is_neutral_site,
    (game ->> 'homeId')::int          as home_team_id,
    game ->> 'homeTeam'               as home_team,
    (game ->> 'homePoints')::int      as home_points,
    (game ->> 'awayId')::int          as away_team_id,
    game ->> 'awayTeam'               as away_team,
    (game ->> 'awayPoints')::int      as away_points,
    game ->> 'venue'                  as venue,
    (game ->> 'attendance')::int      as attendance
from games
