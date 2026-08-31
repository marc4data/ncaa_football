-- One row per game: conditions at kickoff, plus the venue and matchup context CFBD ships
-- alongside them.
--
-- Every one of the twenty-two fields /games/weather publishes is carried through. That is the
-- point of this model rather than an aspiration for it: the endpoint had been landing since
-- August and nothing read it, because no page needed weather and a field nobody's page needs
-- is invisible from the inside — fetched, stored, and never once selected.
--
-- WHY IT IS NOT JOINED TO stg_games HERE. Weather repeats homeTeam/awayTeam/conference/venue
-- that stg_games already carries, and the tempting move is to drop them as redundant. They
-- stay: staging's job is to represent the endpoint faithfully, and a reconciliation test
-- between the two copies is only possible while both exist. Deduplication is a mart decision.
--
-- Season scoping comes from the payload, not the request. /games/weather is fetched per
-- (year, seasonType) and echoes both back on every row, so the model reads the row rather
-- than parsing `params` — one less place for a week-scoped and a season-scoped fetch of the
-- same game to disagree.

with successful_fetches as (

    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_games_weather') }}
    where status_code = 200

),

games as (

    select {{ json_array_elements('payload') }} as game
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('game', 'id') }} as int)            as game_id,
    cast({{ json_get_string('game', 'season') }} as int)        as season,
    cast({{ json_get_string('game', 'week') }} as int)          as week,
    {{ json_get_string('game', 'seasonType') }}                 as season_type,
    cast({{ json_get_string('game', 'startTime') }} as {{ type_timestamp_tz() }})
                                                                as start_at,

    -- Matchup context, by NAME. /games/weather ships no team ids, so anything joining this
    -- to a team dimension joins on a string — the same hazard as /teams/matchup. Carried
    -- verbatim rather than resolved here; resolution needs a season-scoped team map, which
    -- is a mart's job and not a staging model's.
    {{ json_get_string('game', 'homeTeam') }}                   as home_team,
    {{ json_get_string('game', 'homeConference') }}             as home_conference,
    {{ json_get_string('game', 'awayTeam') }}                   as away_team,
    {{ json_get_string('game', 'awayConference') }}             as away_conference,

    cast({{ json_get_string('game', 'venueId') }} as int)       as venue_id,
    {{ json_get_string('game', 'venue') }}                      as venue,
    -- Indoor games still report temperature and humidity — the stadium's, not the sky's. Any
    -- weather-effect analysis has to filter on this or it will average a dome into the rain.
    cast({{ json_get_string('game', 'gameIndoors') }} as boolean) as is_indoors,

    -- Measurements. safe_numeric because these are nullable on old and unplayed games, and a
    -- hard cast turns one missing reading into a failed model run.
    {{ safe_numeric(json_get_string('game', 'temperature')) }}         as temperature_f,
    {{ safe_numeric(json_get_string('game', 'dewPoint')) }}            as dew_point_f,
    {{ safe_numeric(json_get_string('game', 'humidity')) }}            as humidity_pct,
    {{ safe_numeric(json_get_string('game', 'precipitation')) }}       as precipitation_in,
    {{ safe_numeric(json_get_string('game', 'snowfall')) }}            as snowfall_in,
    {{ safe_numeric(json_get_string('game', 'windDirection')) }}       as wind_direction_deg,
    {{ safe_numeric(json_get_string('game', 'windSpeed')) }}           as wind_speed_mph,
    {{ safe_numeric(json_get_string('game', 'pressure')) }}            as pressure_mb,
    {{ safe_numeric(json_get_string('game', 'weatherConditionCode')) }} as weather_condition_code,
    {{ json_get_string('game', 'weatherCondition') }}                  as weather_condition
from games
