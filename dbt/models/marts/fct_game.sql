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

    select
        g.*,
        h.times_known,
        -- TV only: /games/media returns a row per media type, so joining all of them would
        -- multiply each game — the exact fan-out a one-row-per-game grain exists to prevent.
        m.outlet as network,
        -- One poll on purpose, for the same reason.
        hr.rank as home_rank,
        ar.rank as away_rank
    from {{ ref('stg_games') }} g
-- Deduplicated to ONE TV row per game. Simulcasts are real — ABC and SEC Network carry the
-- same game, ESPN and ESPN2 likewise — and joining them all multiplied 18 games into two
-- rows each, breaking the one-row-per-game grain. Caught by the before/after row count,
-- not by an error: a fan-out is a silent correctness bug that still builds green.
left join (
    select game_id, outlet
    from (
        select game_id, outlet,
               row_number() over (partition by game_id order by outlet) as outlet_rank
        from {{ ref('stg_game_media') }}
        where media_type = 'tv'
    ) ranked
    where outlet_rank = 1
) m on m.game_id = g.game_id
left join {{ ref('fct_poll_rank') }} hr
    on hr.season = g.season and hr.season_type = g.season_type and hr.week = g.week
   and hr.team_id = g.home_team_id and hr.poll_name = 'AP Top 25'
left join {{ ref('fct_poll_rank') }} ar
    on ar.season = g.season and ar.season_type = g.season_type and ar.week = g.week
   and ar.team_id = g.away_team_id and ar.poll_name = 'AP Top 25'
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
    g.attendance,
    g.excitement_index,

    -- Broadcast outlet, TV only. /games/media returns a row per media type, so a game on
    -- TV and on a streaming service appears twice; taking the TV row keeps the grain at one
    -- row per game. A game with no TV row has a null network, which is the honest answer
    -- for a game nobody is carrying.
    g.network,

    -- Poll ranks at the time of the game, AP only, and IS_UPSET derived from them.
    --
    -- One poll on purpose: joining every poll would multiply each game by the number of
    -- polls ranking either team, which is precisely the fan-out a grain of "one row per
    -- game" exists to prevent.
    g.home_rank,
    g.away_rank,
    case
        when not g.is_completed then null
        -- An upset is the ranked side losing to a side ranked worse or unranked. Stated as
        -- a column because AC-3.6 forbids the app comparing ranks itself.
        when g.home_points > g.away_points and g.away_rank is not null
             and (g.home_rank is null or g.home_rank > g.away_rank) then true
        when g.away_points > g.home_points and g.home_rank is not null
             and (g.away_rank is null or g.away_rank > g.home_rank) then true
        else false
    end as is_upset
from games g
