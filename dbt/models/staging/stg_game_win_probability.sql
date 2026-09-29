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

-- 🚨 ONE GENERATION PER GAME, AND `playId` CANNOT BE THE DEDUP KEY — A254 (cfdb-main-R-3576).
--
-- THIS CTE USED TO READ `row_number() over (partition by playId order by filename desc)`, which
-- is wrong twice, and both ways were measured before it was changed:
--
--   1. `playId` IS NOT UNIQUE. It is the literal string `'0'` on the terminal "Game ended" row of
--      EVERY game — 2,044 games carry one. Partitioning globally by it collapsed all 2,044 into a
--      SINGLE row, filed under whichever game happened to own the newest filename. Game 401856813
--      lost its last row to game 401858470. That row is not a football play and has no `stg_play`
--      match, so it is excluded below rather than kept.
--
--   2. `playId` IS NOT STABLE. CFBD REISSUES IT, and it renumbers `playNumber` with it. Keeping one
--      row per playId therefore kept EVERY GENERATION of a re-fetched game side by side: game
--      401861970 (UConn at Miami (OH), wk4) held 143 rows for a game whose every fetch reports
--      139. League-wide that was 52 duplicate `(game_id, play_number)` groups across 24 games, all
--      of them 2026 weeks 2-4 — the in-season games a reader can reach.
--
-- 📊 AND THE TWO GENERATIONS DISAGREE ABOUT THE FOOTBALL, which is what made it visible. Of the 52
-- groups, 43 are the feed RENUMBERING (old play 33 "End of 1st quarter" against new play 33, a real
-- snap) and 9 are the same play under a reissued id carrying a DIFFERENT win probability. So the
-- curve crossed 0.5 a different number of times depending on which rows you looked at, and
-- `fct_game_win_probability_summary`'s tie-break — staging's `play_number`, which these duplicates
-- make non-unique — resolved it ARBITRARILY. That is the whole of A253's 8-against-10.
--
-- ⚠️ A183 SAW THE SYMPTOM AND DIAGNOSED IT AS THE FEED NUMBERING TWO REAL PLAYS ALIKE, and
-- concluded "a dedupe would delete a real play and draw a different game". ✅ THE CONCLUSION WAS
-- RIGHT AND THE CAUSE WAS NOT: no single fetch file has ever carried two rows with the same
-- `playNumber` for one game — measured, ZERO groups across every file in `raw_metrics_wp`. The
-- duplicates were never inside a generation, they were BETWEEN generations. So this is not a
-- dedupe on `(game_id, play_number)`, which really would destroy real plays; it is the removal of
-- superseded fetches. A183's derived ordinal in `fct_game_win_probability_play` is left exactly as
-- it is — it costs nothing now that the ties are gone, and it is the guard if CFBD ever does what
-- A183 thought it had done.
--
-- ⚠️ `dense_rank`, NOT `row_number`: the whole newest file is generation 1, not one row of it.
-- Mixing generations within a game would splice two numbering schemes into one game, which is the
-- defect rather than the fix.
--
-- 📊 THE COST, MEASURED AND ACCEPTED: 5 games hold MORE rows in an older fetch than in their
-- newest, totalling 15 rows — and those games are precisely the ones with the most duplicate
-- groups (401856693 drops 6 with 6 duplicate groups; 401866418 drops 6 with 6). The dropped rows
-- ARE the superseded numbering. Filenames are ISO-8601 UTC stamps, so `order by filename desc` is
-- chronological.
current_generation as (

    select row_json
    from (
        select
            row_json,
            dense_rank() over (
                partition by {{ json_get_string('row_json', 'gameId') }}
                order by filename desc
            ) as generation
        from exploded
    ) ranked
    where generation = 1
      -- THE TERMINAL MARKER, NOT A PLAY. See point 1 above: `playId` `'0'`, `playText`
      -- "Game ended", no `stg_play` row to join, and one per game. Keeping it would put 2,044 rows
      -- with a null period and a null elapsed clock onto a chart that positions on elapsed time.
      and {{ json_get_string('row_json', 'playId') }} <> '0'

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
from current_generation
