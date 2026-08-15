-- One row per game, across every season landed in raw.
--
-- Dedup is keyed on the **whole params object**, not on the season alone. The backfill
-- fetches each season twice — once for `seasonType=regular`, once for `postseason` — so
-- deduping per season would silently discard the bowl games. Keying on params generalises:
-- one surviving file per distinct request, whatever dimensions that request had.
--
-- JSON access goes through the dispatched macros (see macros/json.sql); the dedup uses a
-- window function rather than Postgres' `distinct on`, which Spark has no equivalent for.

with successful_fetches as (

    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (
            partition by params
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_games') }}
    where status_code = 200

),

games as (

    select {{ json_array_elements('payload') }} as game
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('game', 'id') }} as int)              as game_id,
    cast({{ json_get_string('game', 'season') }} as int)          as season,
    cast({{ json_get_string('game', 'week') }} as int)            as week,
    {{ json_get_string('game', 'seasonType') }}                   as season_type,
    cast({{ json_get_string('game', 'startDate') }} as {{ type_timestamp_tz() }}) as start_date,
    cast({{ json_get_string('game', 'completed') }} as boolean)   as is_completed,
    cast({{ json_get_string('game', 'conferenceGame') }} as boolean) as is_conference_game,
    cast({{ json_get_string('game', 'neutralSite') }} as boolean) as is_neutral_site,
    cast({{ json_get_string('game', 'homeId') }} as int)          as home_team_id,
    {{ json_get_string('game', 'homeTeam') }}                     as home_team,
    cast({{ json_get_string('game', 'homePoints') }} as int)      as home_points,
    {{ json_get_string('game', 'homeClassification') }}           as home_classification,
    cast({{ json_get_string('game', 'awayId') }} as int)          as away_team_id,
    {{ json_get_string('game', 'awayTeam') }}                     as away_team,
    cast({{ json_get_string('game', 'awayPoints') }} as int)      as away_points,
    {{ json_get_string('game', 'awayClassification') }}           as away_classification,
    {{ json_get_string('game', 'venue') }}                        as venue,
    cast({{ json_get_string('game', 'attendance') }} as int)      as attendance
from games
