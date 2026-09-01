-- Play-level stat lines: one row per (play, athlete, stat type).
--
-- THE BRIDGE FROM A PLAY TO THE PLAYERS INVOLVED IN IT. stg_play has a play_text describing
-- what happened; this has the structured version — which athlete recorded which stat on
-- which play. A sack on play 401628319101866901 is a row here naming Quandarrius Robinson.
--
-- SEVERAL ROWS PER PLAY IS NORMAL, not a duplicate: a completed pass produces a passer, a
-- receiver and a reception, each its own row. The grain is the athlete and the stat type
-- together, and both are needed — one athlete can record two different stats on one play.
--
-- `playId` JOINS TO stg_play.play_id and both are strings. `driveId` likewise joins to
-- stg_drive. Between the three models a play can be traced from its drive to the people in
-- it without a single name comparison, which is rare in this API.
--
-- `stat` IS A NUMBER HERE, unlike the box-score models where every stat value is a string.
-- The reason is that this endpoint reports one measure per row rather than a category with
-- a compound value like "4-9", so there is nothing to parse.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_plays_stats') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'playId') }},
                    {{ json_get_string('row_json', 'athleteId') }},
                    {{ json_get_string('row_json', 'statType') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('row_json', 'playId') }}                 as play_id,
    {{ json_get_string('row_json', 'driveId') }}                as drive_id,
    cast({{ json_get_string('row_json', 'gameId') }} as bigint) as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)    as season,
    cast({{ json_get_string('row_json', 'week') }} as int)      as week,

    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'conference') }}             as conference,
    {{ json_get_string('row_json', 'opponent') }}               as opponent,
    cast({{ json_get_string('row_json', 'teamScore') }} as int)     as team_score,
    cast({{ json_get_string('row_json', 'opponentScore') }} as int) as opponent_score,

    cast({{ json_get_string('row_json', 'period') }} as int)    as period,
    cast({{ json_get_nested_string('row_json', ['clock', 'minutes']) }} as int)
                                                                as clock_minutes,
    cast({{ json_get_nested_string('row_json', ['clock', 'seconds']) }} as int)
                                                                as clock_seconds_part,
    cast({{ json_get_string('row_json', 'yardsToGoal') }} as int) as yards_to_goal,
    cast({{ json_get_string('row_json', 'down') }} as int)      as down,
    cast({{ json_get_string('row_json', 'distance') }} as int)  as distance,

    {{ json_get_string('row_json', 'athleteId') }}              as athlete_id,
    {{ json_get_string('row_json', 'athleteName') }}            as athlete_name,
    {{ json_get_string('row_json', 'statType') }}               as stat_type,
    -- A NUMBER on this endpoint, unlike the box scores. See the header.
    {{ safe_numeric(json_get_string('row_json', 'stat')) }}     as stat
from deduped
