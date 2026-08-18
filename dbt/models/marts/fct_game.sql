{{ config(materialized='table') }}

-- One row per game. A promotion of stg_games — the grain was already correct — with
-- conformed keys attached.
--
-- This model owns the date-era logic. CFBD records kickoff times only from 2001; earlier
-- games are stored at midnight UTC as date-only values, and converting those to a local
-- zone shifts 66,496 games back a day. Everything downstream reads game_date and
-- kickoff_time_known from here rather than recomputing and getting it wrong differently.

with season_has_times as (

    select season, bool_or({{ utc_time_of_day('start_date') }} <> '00:00:00') as times_known
    from {{ ref('stg_games') }}
    group by season

),

games as (

    select g.*, h.times_known
    from {{ ref('stg_games') }} g
    join season_has_times h on h.season = g.season

)

select
    {{ surrogate_key(['g.game_id']) }} as game_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    {{ surrogate_key(['g.season', 'g.season_type', 'g.week']) }} as week_sk,
    {{ surrogate_key(['g.season', 'g.home_team_id']) }} as home_team_sk,
    {{ surrogate_key(['g.season', 'g.away_team_id']) }} as away_team_sk,
    g.home_team_id,
    g.away_team_id,
    g.home_team,
    g.away_team,
    g.home_classification,
    g.away_classification,
    g.start_date,
    case
        when g.times_known then {{ to_local_date('g.start_date') }}
        else {{ to_utc_date('g.start_date') }}
    end as game_date,
    g.times_known as kickoff_time_known,
    g.is_completed,
    g.is_conference_game,
    g.is_neutral_site,
    g.home_points,
    g.away_points,
    -- Venue name, not a key: /games carries no venue id, so a dim_venue join would be
    -- name-based and lossy. The name is what pages render anyway.
    g.venue,
    g.attendance
from games g
