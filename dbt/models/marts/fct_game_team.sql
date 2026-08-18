{{ config(materialized='table') }}

-- One row per (game, team) — exactly two per game. The normalized team-game fact.
--
-- Two sources: the game spine (every game, including those with no box score) and
-- /games/teams box scores (2024+ only, and not every game). LEFT joined, so a game without
-- a box score still produces its two rows with null stats — dropping them would silently
-- shrink the schedule.
--
-- Only a curated subset of the 35 EAV categories is pivoted. The rest stay in
-- stg_game_team_stat, long and verbatim. Each pivoted column is a parsing decision, and
-- parsing 35 of them for pages that read twelve is how a model becomes unmaintainable.

with team_games as (

    select
        game_sk, game_id, season, week, season_type, week_sk, game_date, kickoff_time_known,
        is_completed, is_conference_game, is_neutral_site, venue, attendance,
        home_team_sk as team_sk, home_team_id as team_id, home_team as team,
        home_classification as classification,
        away_team_sk as opponent_team_sk, away_team_id as opponent_team_id,
        away_team as opponent, away_classification as opponent_classification,
        home_points as points_for, away_points as points_against,
        true as is_home
    from {{ ref('fct_game') }}

    union all

    select
        game_sk, game_id, season, week, season_type, week_sk, game_date, kickoff_time_known,
        is_completed, is_conference_game, is_neutral_site, venue, attendance,
        away_team_sk, away_team_id, away_team, away_classification,
        home_team_sk, home_team_id, home_team, home_classification,
        away_points, home_points,
        false as is_home
    from {{ ref('fct_game') }}

),

box as (

    select
        game_id,
        team_id,
        max(case when stat_category = 'firstDowns'          then {{ safe_int('stat_raw') }} end) as first_downs,
        max(case when stat_category = 'totalYards'          then {{ safe_int('stat_raw') }} end) as total_yards,
        max(case when stat_category = 'rushingYards'        then {{ safe_int('stat_raw') }} end) as rushing_yards,
        max(case when stat_category = 'netPassingYards'     then {{ safe_int('stat_raw') }} end) as passing_yards,
        max(case when stat_category = 'rushingAttempts'     then {{ safe_int('stat_raw') }} end) as rushing_attempts,
        max(case when stat_category = 'turnovers'           then {{ safe_int('stat_raw') }} end) as turnovers,
        max(case when stat_category = 'interceptions'       then {{ safe_int('stat_raw') }} end) as interceptions,
        max(case when stat_category = 'fumblesLost'         then {{ safe_int('stat_raw') }} end) as fumbles_lost,
        -- Compound values, split rather than stored as text: "4-9" is two facts.
        max(case when stat_category = 'thirdDownEff'
                 then {{ safe_int(split_at('stat_raw', '-', 1)) }} end) as third_down_conversions,
        max(case when stat_category = 'thirdDownEff'
                 then {{ safe_int(split_at('stat_raw', '-', 2)) }} end) as third_down_attempts,
        max(case when stat_category = 'fourthDownEff'
                 then {{ safe_int(split_at('stat_raw', '-', 1)) }} end) as fourth_down_conversions,
        max(case when stat_category = 'fourthDownEff'
                 then {{ safe_int(split_at('stat_raw', '-', 2)) }} end) as fourth_down_attempts,
        max(case when stat_category = 'totalPenaltiesYards'
                 then {{ safe_int(split_at('stat_raw', '-', 1)) }} end) as penalties,
        max(case when stat_category = 'totalPenaltiesYards'
                 then {{ safe_int(split_at('stat_raw', '-', 2)) }} end) as penalty_yards,
        max(case when stat_category = 'possessionTime'
                 then {{ safe_int(split_at('stat_raw', ':', 1)) }} * 60
                    + {{ safe_int(split_at('stat_raw', ':', 2)) }} end) as possession_seconds
    from {{ ref('stg_game_team_stat') }}
    group by game_id, team_id

)

select
    {{ surrogate_key(['g.game_id', 'g.team_id']) }} as game_team_sk,
    g.game_sk,
    g.game_id,
    g.team_sk,
    g.team_id,
    g.team,
    g.classification,
    g.opponent_team_sk,
    g.opponent_team_id,
    g.opponent,
    g.opponent_classification,
    g.season,
    g.week,
    g.season_type,
    g.week_sk,
    g.game_date,
    g.kickoff_time_known,
    g.is_home,
    g.is_neutral_site,
    g.is_conference_game,
    g.is_completed,
    g.venue,
    g.attendance,
    g.points_for,
    g.points_against,
    case
        when g.points_for is null or g.points_against is null then null
        else g.points_for - g.points_against
    end as margin,
    case
        when not g.is_completed or g.points_for is null or g.points_against is null then null
        when g.points_for > g.points_against then 'W'
        when g.points_for < g.points_against then 'L'
        else 'T'
    end as result,
    b.first_downs, b.total_yards, b.rushing_yards, b.passing_yards, b.rushing_attempts,
    b.turnovers, b.interceptions, b.fumbles_lost,
    b.third_down_conversions, b.third_down_attempts,
    b.fourth_down_conversions, b.fourth_down_attempts,
    b.penalties, b.penalty_yards, b.possession_seconds,
    b.game_id is not null as has_box_score
from team_games g
left join box b on b.game_id = g.game_id and b.team_id = g.team_id
