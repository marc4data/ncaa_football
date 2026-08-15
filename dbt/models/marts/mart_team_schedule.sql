{{ config(materialized='table') }}

-- One row per team per game: the schedule from a single team's point of view.
--
-- The first model built for an analyst rather than for the site, and the first demand on
-- the demand-driven modeling policy. `stg_games` stores one row per matchup, which answers
-- "who played in this game" but not "what is Oregon's season" without a union every time.
-- This does that union once.
--
-- Covers every season landed, including seasons not yet played: a 2026 row has a kickoff
-- time and an opponent but no result, which is exactly what a schedule is before it starts.

-- CFBD records kickoff times only from 2001 on; every game before that is stored at
-- midnight UTC as a date-only value. Converting those to Eastern would shift 66,496 games
-- back a day — the first game ever played would read 1869-11-05 instead of 11-06.
--
-- The era is detected from the data rather than hardcoded, and the ambiguity is real:
-- 00:00 UTC is *also* a genuine 8pm ET kickoff, so the same literal timestamp means
-- "date unknown" in 1900 and "8pm Saturday" in 2024. Per-season detection resolves it for
-- every season that has any times at all.
with season_has_times as (

    select season, bool_or(start_date::time <> '00:00:00') as times_known
    from {{ ref('stg_games') }}
    group by season

),

team_games as (

    select
        game_id, season, week, season_type, start_date, is_completed, is_conference_game,
        is_neutral_site, venue, attendance,
        home_team_id       as team_id,
        home_team          as team,
        home_classification as classification,
        home_points        as points_for,
        away_team_id       as opponent_id,
        away_team          as opponent,
        away_classification as opponent_classification,
        away_points        as points_against,
        false              as is_away
    from {{ ref('stg_games') }}

    union all

    select
        game_id, season, week, season_type, start_date, is_completed, is_conference_game,
        is_neutral_site, venue, attendance,
        away_team_id       as team_id,
        away_team          as team,
        away_classification as classification,
        away_points        as points_for,
        home_team_id       as opponent_id,
        home_team          as opponent,
        home_classification as opponent_classification,
        home_points        as points_against,
        true               as is_away
    from {{ ref('stg_games') }}

)

select
    g.season::text || '-' || g.game_id::text || '-' || g.team_id::text as team_game_key,
    g.season,
    g.week,
    g.season_type,
    g.game_id,
    g.team_id,
    g.team,
    t.conference,
    coalesce(t.classification, g.classification) as classification,
    g.opponent_id,
    g.opponent,
    o.conference as opponent_conference,
    coalesce(o.classification, g.opponent_classification) as opponent_classification,
    g.start_date,
    -- The site and any analysis both want local calendar day, not a UTC timestamp.
    case
        when h.times_known then (g.start_date at time zone 'America/New_York')::date
        else (g.start_date at time zone 'UTC')::date
    end as game_date,
    h.times_known as kickoff_time_known,
    case when g.is_neutral_site then 'neutral' when g.is_away then 'away' else 'home' end as venue_role,
    g.is_conference_game,
    g.is_neutral_site,
    g.venue,
    g.attendance,
    g.is_completed,
    g.points_for,
    g.points_against,
    case
        when not g.is_completed or g.points_for is null or g.points_against is null then null
        when g.points_for > g.points_against then 'W'
        when g.points_for < g.points_against then 'L'
        else 'T'
    end as result,
    case
        when g.points_for is null or g.points_against is null then null
        else g.points_for - g.points_against
    end as margin
from team_games g
join season_has_times h on h.season = g.season
left join {{ ref('stg_teams') }} t on t.team_id = g.team_id     and t.season = g.season
left join {{ ref('stg_teams') }} o on o.team_id = g.opponent_id and o.season = g.season
