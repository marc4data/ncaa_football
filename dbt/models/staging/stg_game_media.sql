-- CFBD /games/media — which outlet is carrying a game.
--
-- One row per (game, media type, outlet): a game on both TV and a streaming service appears
-- twice, and a game on two networks appears twice within `tv`. A consumer wanting "the
-- network" must pick, rather than assume uniqueness.
--
-- ALL SIX PUBLISHED FIELDS ARE CARRIED. The endpoint also ships homeTeam, awayTeam,
-- homeConference, awayConference, startTime and isStartTimeTBD; those are on the /games spine
-- already and adding them here is a mart's deduplication decision, not staging's — see the
-- coverage matrix, which counts this endpoint honestly rather than pretending it is complete.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_games_media') }}
    where status_code = 200

),

exploded as (

    select
        filename,
        {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

-- DEDUP ON THE ENTITY, NOT ON `params`.
--
-- The usual staging pattern keeps the newest response PER REQUEST — `partition by params`.
-- That is correct only while different requests return disjoint games, and here they do not:
-- /games/media is fetched season-scoped by the weekly refresh AND week-scoped by the scores
-- refresh, so `{"year":"2026","seasonType":"regular"}` and `{"week":"1","year":"2026",
-- "seasonType":"regular"}` both return week 1. Two distinct params, same games, and a
-- params-level dedup cannot see it: 111 duplicated (game, type, outlet) triples in production.
--
-- This is exactly the failure that put 211 duplicate game_ids into fct_game, in a second
-- endpoint. It went unnoticed because fct_game happens to rank outlets per game for an
-- unrelated reason — multiple networks carrying one game — and that guard absorbed these
-- duplicates on the way past. A defect that is invisible because something downstream
-- coincidentally defends against it is still a defect; the next consumer will not.
--
-- Newest file wins, same as elsewhere: filenames are UTC timestamps, so lexical order is
-- chronological order.
deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'id') }},
                    {{ json_get_string('row_json', 'mediaType') }},
                    {{ json_get_string('row_json', 'outlet') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'id') }} as bigint)   as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)  as season,
    cast({{ json_get_string('row_json', 'week') }} as int)    as week,
    {{ json_get_string('row_json', 'seasonType') }}           as season_type,
    {{ json_get_string('row_json', 'mediaType') }}            as media_type,
    {{ json_get_string('row_json', 'outlet') }}               as outlet,

    -- THE MATCHUP AND THE KICKOFF, which this model dropped. A broadcast listing without the
    -- teams is only usable through a join to stg_games, and `startTime` here is the reason
    -- the endpoint is classified PREGAME rather than historical: it moves as networks fix
    -- their windows.
    {{ json_get_string('row_json', 'homeTeam') }}             as home_team,
    {{ json_get_string('row_json', 'homeConference') }}       as home_conference,
    {{ json_get_string('row_json', 'awayTeam') }}             as away_team,
    {{ json_get_string('row_json', 'awayConference') }}       as away_conference,
    cast({{ json_get_string('row_json', 'startTime') }} as {{ type_timestamp_tz() }})
                                                              as start_at,
    -- TRUE MEANS THE TIME IS A PLACEHOLDER, not that it is missing. A game listed at noon
    -- with this set is not scheduled for noon; it is unscheduled, and a schedule page that
    -- ignores the flag will state a kickoff that nobody announced.
    cast({{ json_get_string('row_json', 'isStartTimeTBD') }} as boolean)
                                                              as is_start_time_tbd
from deduped
