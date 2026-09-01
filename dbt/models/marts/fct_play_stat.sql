{{ config(materialized='table') }}

-- One row per (play, athlete, stat type) — the bridge from a play to the players in it.
--
-- This is what makes the Players page's play-level drill-down possible: stg_play has
-- play_text describing what happened, and this has the structured version — which athlete
-- recorded which stat on which play.
--
-- SEVERAL ROWS PER PLAY IS NORMAL, not a duplicate. A completed pass produces a passer, a
-- receiver and a reception, each its own row; one athlete can record two different stats on
-- the same play, which is why the grain needs both the athlete and the stat type.
--
-- THIS FACT WAS TRUNCATED UPSTREAM FOR MONTHS, AND THE FIX IS WORTH KNOWING ABOUT.
--
-- CFBD's spec says /plays/stats is "limited to 2,000 records" per request. cfdb fetched it
-- per season-week, and a week has far more than that, so every request returned exactly
-- 2,000 rows and stopped — 200 status, no indication anything was dropped. Coverage was 375
-- games of the 3,410 with box scores, about 11%, and the survivors were whatever the API
-- returned first: 118 of the 177 covered 2024 games were SEC, which is row ordering rather
-- than a fact about football.
--
-- Nothing detected it for the reason silent truncation is always missed: a 200 response
-- carrying 2,000 rows looks exactly like a complete one.
--
-- FIXED by fanning the endpoint out per game, which is the only scope that fits under the
-- cap. Measured after the backfill: 375,925 rows over 1,884 games — 5.4x the data — with
-- 2024 conference coverage now Big Ten 151, ACC 149, SEC 144, Big 12 127, which is what an
-- unbiased sample of a season looks like. Per game it averages 199.5 stat lines and peaks at
-- 356, an order of magnitude below the ceiling.
--
-- assert_play_stats_are_not_truncated_at_the_api_cap guards it at ERROR severity, asserting
-- per GAME rather than per week — the unit of truncation moved when the fetch did.
--
-- COVERAGE IS STILL NOT UNIVERSAL, and absence must be read as unknown rather than as zero.
-- The fan-out runs over completed FBS games, which is the project's scope, so a game with no
-- rows here is one cfdb did not ask about — not a game in which nobody did anything.

with play_stats as (

    select * from {{ ref('stg_play_stat') }}

),

resolved as (

    select
        s.*,
        p.season_type,
        p.game_date,
        -- down, distance, yards_to_goal, period and the clock are ALREADY on the stat row —
        -- /plays/stats repeats the play's situation on every line it emits. They are taken
        -- from there rather than from fct_play, which is why only the DERIVED situation
        -- columns are pulled across. assert_play_stat_situation_agrees_with_the_play checks
        -- the two sources have not drifted.
        p.down_distance_display,
        p.distance_bucket,
        p.field_zone,
        p.play_type,
        p.play_text,
        p.yards_gained,
        p.is_scoring_play,
        p.ppa,
        p.offense_team_id,
        p.defense_team_id,
        a.athlete_sk,
        t.team_id
    from play_stats s
    -- One row per play, so this cannot fan out.
    left join {{ ref('fct_play') }} p on p.play_id = s.play_id
    left join {{ ref('dim_team') }} t on t.season = s.season and t.school = s.team
    -- Three columns, matching dim_athlete's grain.
    left join {{ ref('dim_athlete') }} a
        on  a.season    = s.season
        and a.player_id = s.athlete_id
        and a.team      = s.team

)

select
    {{ surrogate_key(['play_id', 'athlete_id', 'stat_type']) }} as play_stat_sk,
    play_id,
    drive_id,
    game_id,
    season,
    week,
    season_type,
    game_date,

    athlete_id                                            as player_id,
    athlete_name                                          as player_name,
    -- Same construction as everywhere else, so the page can link without a lookup.
    {{ to_slug('athlete_name') }} || '-' || athlete_id     as player_slug,
    athlete_sk,
    athlete_sk is not null                                as has_athlete_dimension,

    team,
    team_id,
    conference,
    opponent,
    team_score,
    opponent_score,

    stat_type,
    -- A NUMBER on this endpoint, unlike the box scores: it reports one measure per row
    -- rather than a category with a compound value, so there is nothing to parse.
    stat,

    -- Play context, carried so the drill-down can filter without joining (G-2: the site
    -- reads one relation per query).
    period,
    clock_minutes,
    clock_seconds_part,
    down,
    distance,
    yards_to_goal,
    down_distance_display,
    distance_bucket,
    field_zone,
    play_type,
    play_text,
    yards_gained,
    is_scoring_play,
    ppa,
    offense_team_id,
    defense_team_id
from resolved
