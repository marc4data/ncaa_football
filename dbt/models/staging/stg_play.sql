-- Play-by-play: one row per play. 619,113 plays across 2024-2026, the highest-volume model
-- in the project by an order of magnitude.
--
-- A VIEW, DELIBERATELY, AND HERE IS THE TRIGGER FOR CHANGING THAT. A full unnest of
-- raw_plays with field extraction measures 2.4 seconds on the droplet's two vCPUs — cheap
-- while nothing consumes this model. It stops being cheap the moment a mart references it
-- more than once: a window function is an optimization fence, and re-inlining a 619k-row
-- unnest per reference is exactly what made fct_game fail to finish in 22 minutes when
-- stg_games was still a view. THE FIRST MART THAT READS THIS TWICE SHOULD MATERIALIZE IT AS
-- A TABLE. Until then a view costs nothing to build and nothing to keep.
--
-- SCOPE IS 2024-2026 BY THE DATA, NOT BY A FILTER. CLAUDE.md limits play-by-play to those
-- three seasons and the backfill honoured it, so raw holds exactly them. Adding a season
-- predicate here would encode the same rule twice and let the two disagree.
--
-- `clock` IS AN OBJECT, NOT A STRING — minutes and seconds as separate integers, with no
-- combined form. Both are carried plus a derived `clock_seconds`, because ordering plays
-- within a period by "12:50" as text sorts 9:00 after 12:50.
--
-- IDS ARE STRINGS AND STAY STRINGS. `id` is 401643697101849908 — eighteen digits, beyond a
-- 32-bit int and right at the edge of comfort for a bigint that CFBD never promised is
-- numeric. `driveId` likewise. `gameId` IS typed, because it is the join to stg_games and
-- every other model treats it as a bigint.
--
-- `scoring` MARKS THE PLAY THAT SCORED, not whether the game had scoring. A drive's points
-- are on the drive, not summed from here.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_plays') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as play
    from successful_fetches

),

deduped as (

    select play
    from (
        select
            play,
            -- On the play id alone: a week-scoped and a season-scoped fetch of the same
            -- week would return the same plays under different params, which params-level
            -- dedup cannot see. That is the /games and /games/media failure, and at 619k
            -- rows it would be far harder to spot.
            row_number() over (
                partition by {{ json_get_string('play', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('play', 'id') }}                        as play_id,
    cast({{ json_get_string('play', 'gameId') }} as bigint)    as game_id,
    {{ json_get_string('play', 'driveId') }}                   as drive_id,
    cast({{ json_get_string('play', 'driveNumber') }} as int)  as drive_number,
    cast({{ json_get_string('play', 'playNumber') }} as int)   as play_number,

    {{ json_get_string('play', 'offense') }}                   as offense,
    {{ json_get_string('play', 'offenseConference') }}         as offense_conference,
    cast({{ json_get_string('play', 'offenseScore') }} as int) as offense_score,
    {{ json_get_string('play', 'defense') }}                   as defense,
    {{ json_get_string('play', 'defenseConference') }}         as defense_conference,
    cast({{ json_get_string('play', 'defenseScore') }} as int) as defense_score,
    {{ json_get_string('play', 'home') }}                      as home_team,
    {{ json_get_string('play', 'away') }}                      as away_team,

    cast({{ json_get_string('play', 'period') }} as int)       as period,
    cast({{ json_get_nested_string('play', ['clock', 'minutes']) }} as int) as clock_minutes,
    cast({{ json_get_nested_string('play', ['clock', 'seconds']) }} as int) as clock_seconds_part,
    -- Derived so plays can be ordered within a period. Text ordering puts 9:00 after 12:50.
    cast({{ json_get_nested_string('play', ['clock', 'minutes']) }} as int) * 60
        + cast({{ json_get_nested_string('play', ['clock', 'seconds']) }} as int)
                                                               as clock_seconds,

    cast({{ json_get_string('play', 'offenseTimeouts') }} as int) as offense_timeouts,
    cast({{ json_get_string('play', 'defenseTimeouts') }} as int) as defense_timeouts,
    cast({{ json_get_string('play', 'yardline') }} as int)     as yardline,
    cast({{ json_get_string('play', 'yardsToGoal') }} as int)  as yards_to_goal,
    cast({{ json_get_string('play', 'down') }} as int)         as down,
    cast({{ json_get_string('play', 'distance') }} as int)     as distance,
    cast({{ json_get_string('play', 'yardsGained') }} as int)  as yards_gained,
    cast({{ json_get_string('play', 'scoring') }} as boolean)  as is_scoring_play,

    {{ json_get_string('play', 'playType') }}                  as play_type,
    {{ json_get_string('play', 'playText') }}                  as play_text,
    {{ safe_numeric(json_get_string('play', 'ppa')) }}         as ppa,
    cast({{ json_get_string('play', 'wallclock') }} as {{ type_timestamp_tz() }})
                                                               as wallclock_at
from deduped
