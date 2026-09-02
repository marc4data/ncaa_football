-- `spread` IS ALWAYS ZERO, AND IT IS CFBD'S ZERO, NOT OURS. R-089, investigated 2026-09-02.
--
-- The column has cardinality 1 across all 263,539 rows: non-null everywhere, one distinct
-- value, 0. That is the shape of an unnest bug — a key read from the wrong level of the
-- payload usually presents exactly like this — so it was checked at the source rather than
-- assumed either way.
--
-- It is not an unnest bug. The raw response carries "spread": 0 on every play: 265,253 plays
-- across 1,715 games in raw_metrics_wp, one distinct value. The model reads what the endpoint
-- sends, and the endpoint sends zero.
--
-- No fix exists on this side. Recorded here so the next person to notice the cardinality does
-- not spend the afternoon re-deriving it, and so that if CFBD ever starts populating it the
-- change shows up as a cardinality that is no longer 1.

-- In-game win probability: one row per (game, play). The probability series through a game.
--
-- THE THIRD AND LAST WIN PROBABILITY IN THIS PROJECT, and they are three different things:
--
--   stg_game_pregame_wp        forecast BEFORE kickoff, a snapshot series as the market moves
--   stg_game_win_probability   the live series, one value per play  <- this model
--   stg_game_box_info          the single POSTGAME figure, retrospective
--
-- Reading any one as another is an easy and invisible mistake, which is why none of them is
-- called `win_probability` alone.
--
-- IT CARRIES A REAL playId that joins to stg_play, so a probability swing can be traced to
-- the play that caused it without a name or clock comparison. That makes this the natural
-- bridge between the play-by-play and the game's narrative.
--
-- `homeBall` IS WHICH SIDE HAS POSSESSION, not which side is favoured. A drive by the away
-- team with homeBall false and homeWinProbability 0.9 is a losing team with the ball.
--
-- Fetched one game at a time, so `gameId` IS on the payload here — unlike
-- /game/box/advanced, which names its game only in the request.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_metrics_wp') }}
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
                partition by {{ json_get_string('row_json', 'playId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('row_json', 'playId') }}                 as play_id,
    cast({{ json_get_string('row_json', 'gameId') }} as bigint) as game_id,
    cast({{ json_get_string('row_json', 'playNumber') }} as int) as play_number,
    cast({{ json_get_string('row_json', 'homeId') }} as int)    as home_team_id,
    {{ json_get_string('row_json', 'home') }}                   as home_team,
    cast({{ json_get_string('row_json', 'awayId') }} as int)    as away_team_id,
    {{ json_get_string('row_json', 'away') }}                   as away_team,
    cast({{ json_get_string('row_json', 'homeScore') }} as int) as home_score,
    cast({{ json_get_string('row_json', 'awayScore') }} as int) as away_score,
    cast({{ json_get_string('row_json', 'down') }} as int)      as down,
    cast({{ json_get_string('row_json', 'distance') }} as int)  as distance,
    cast({{ json_get_string('row_json', 'yardLine') }} as int)  as yard_line,
    -- Possession, not favouritism. See the header.
    cast({{ json_get_string('row_json', 'homeBall') }} as boolean) as home_has_ball,
    {{ safe_numeric(json_get_string('row_json', 'homeWinProbability')) }}
                                                                as home_win_probability,
    {{ safe_numeric(json_get_string('row_json', 'spread')) }}   as spread,
    {{ json_get_string('row_json', 'playText') }}               as play_text
from deduped
