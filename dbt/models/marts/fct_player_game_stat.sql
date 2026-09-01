{{ config(materialized='table') }}

-- One row per (game, team, category, stat type, athlete) — the player box score, long.
--
-- 1,266,259 rows over 3,410 games and 24,600 athletes. Box scores are `recent` scope, so
-- this starts at 2024 and is 20 seasons shallower than fct_player_season_stat. That is the
-- honest shape of the Players page: deep season history, recent game detail.
--
-- LONG, NOT PIVOTED, for the reason the staging model is: type names are open-ended and
-- category-specific, and every enumeration is a decision to silently drop whatever CFBD adds
-- next.
--
-- THE SOURCE HAS NEITHER A SEASON NOR A TEAM ID. /games/players ships a game id and a team
-- NAME and nothing else — unlike /games/teams, which carries teamId. Both are resolved here,
-- which is the work this mart exists to do:
--
--   season, week, dates and the opponent come from fct_game   100.00% matched
--   team_id from dim_team on (season, school)                  99.74% matched
--
-- The 3,318 unmatched team rows are the usual non-FBS programmes absent from /teams. They
-- keep their row and their name; team_id is null and that is not a join failure.
--
-- THREE VALUE SHAPES, AND ONLY ONE OF THEM IS A NUMBER. Measured across all 1,266,259:
--
--   1,240,096  a plain number          "58"
--      25,519  a made/attempted pair   "12/31"   passing C/ATT, kicking FG, kicking XP
--         644  the literal "--"        exclusively passing QBR, meaning not computed
--
-- So `stat_value` carries the plain numbers, `stat_made` and `stat_attempted` split the
-- pairs, and all three are null for "--". `stat_raw` always holds what arrived, so a fourth
-- shape appearing upstream is visible as a row with a raw value and no parsed one, rather
-- than as a silent null.
--
-- Splitting the pair rather than leaving it a string is the difference between a page that
-- can show completion percentage and one that can only print "12/31". "Made" covers all
-- three types correctly: a completion is a pass made.

with box as (

    select * from {{ ref('stg_game_player_stat') }}

),

with_game as (

    select
        b.*,
        g.season,
        g.week,
        g.season_type,
        g.game_date,
        g.start_date,
        g.is_completed,
        g.is_neutral_site,
        -- The other side, from this row's perspective. home_away is on the box-score row, so
        -- no comparison against team names is needed and a rename upstream cannot break it.
        case when b.home_away = 'home' then g.away_team else g.home_team end as opponent,
        case when b.home_away = 'home' then g.away_team_id else g.home_team_id end
            as opponent_team_id
    from box b
    join {{ ref('fct_game') }} g on g.game_id = b.game_id

),

resolved as (

    select
        w.*,
        t.team_id,
        a.athlete_sk
    from with_game w
    left join {{ ref('dim_team') }} t
        on t.season = w.season and t.school = w.team
    -- Three columns, matching dim_athlete's grain. Two would fan out the dual-roster players.
    left join {{ ref('dim_athlete') }} a
        on  a.season    = w.season
        and a.player_id = w.athlete_id
        and a.team      = w.team

)

select
    {{ surrogate_key(['game_id', 'team', 'stat_category', 'stat_type', 'athlete_id']) }}
        as player_game_stat_sk,
    game_id,
    season,
    week,
    season_type,
    game_date,
    start_date,
    is_completed,
    is_neutral_site,

    athlete_id                                            as player_id,
    athlete_name                                          as player_name,
    -- Same construction as dim_athlete.athlete_slug and fct_player_season_stat.player_slug,
    -- so all three agree without any of them reading the others.
    {{ to_slug('athlete_name') }} || '-' || athlete_id     as player_slug,
    athlete_sk,
    athlete_sk is not null                                as has_athlete_dimension,

    team,
    team_id,
    conference,
    home_away,
    points                                                as team_points,
    opponent,
    opponent_team_id,

    stat_category,
    stat_type,
    stat_raw,
    -- Plain numbers only. safe_numeric already yields NULL for anything that is not one,
    -- in both dialects, so "12/31" and "--" fall through without a guard of their own.
    {{ safe_numeric('stat_raw') }}                        as stat_value,
    -- The pair, split. The LIKE guard is load-bearing rather than decorative: without it
    -- split_at returns the whole string for a plain number, and every "58" would report
    -- itself as 58 made.
    --
    -- LIKE and split_at rather than a regex: Postgres' `~` does not exist in Spark, and
    -- this model must build on both.
    case when stat_raw like '%/%'
         then {{ safe_numeric(split_at('stat_raw', '/', 1)) }} end as stat_made,
    case when stat_raw like '%/%'
         then {{ safe_numeric(split_at('stat_raw', '/', 2)) }} end as stat_attempted
from resolved
