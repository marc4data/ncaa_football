{{ config(materialized='table') }}

-- Elo per team per week. R-083, the half that did not land in prompt 030.
--
-- NO NEW API CALLS. stg_games carries home_pregame_elo / home_postgame_elo /
-- away_pregame_elo / away_postgame_elo — a rating per team per GAME, which is a rating per
-- team per WEEK. The project had recorded that a weekly rating series required re-fetching
-- /ratings/elo with a week parameter. It did not; the games spine had carried it all along,
-- unread.
--
-- PREGAME OR POSTGAME IS A REAL CHOICE AND BOTH ARE CARRIED.
--
--   pregame_elo   the rating the team took INTO that week's game
--   postgame_elo  the rating it left with
--
-- DEFAULT TO pregame_elo for anything rendered beside a fixture, for the same reason
-- fct_team_record_week carries the record LEADING INTO a week: a rating that already contains
-- the result of the game you are looking at is the off-by-one R-084 exists to prevent. Use
-- postgame_elo when the question is "what did this game do to them", which is a different
-- question and a legitimate one.
--
-- NULLS ARE CARRIED, NOT INTERPOLATED. About 39% of games have no Elo at all, and a team on a
-- bye has no game that week. An interpolated rating is a line that never happened, which is
-- precisely why the Trends tab was blocked rather than approximated.
--
-- `elo_carried_forward` IS THE ONE EXCEPTION, AND IT IS NAMED SO IT CANNOT BE MISTAKEN FOR A
-- MEASUREMENT. Elo genuinely does not move without a game, so the last observed postgame
-- rating is the team's actual rating through a bye — that is carrying a known value forward,
-- not inventing an intermediate one. It is a separate column precisely so a chart chooses
-- explicitly between a line with honest gaps and a step function, rather than the model
-- choosing for it.

with spine as (

    select * from {{ ref('dim_team_week') }}

),

team_games as (

    -- One row per team per game, with that side's Elo.
    select
        season, season_type, week, home_team_id as team_id, game_id,
        home_pregame_elo as pregame_elo, home_postgame_elo as postgame_elo
    from {{ ref('fct_game') }}
    where home_team_id is not null

    union all

    select
        season, season_type, week, away_team_id, game_id,
        away_pregame_elo, away_postgame_elo
    from {{ ref('fct_game') }}
    where away_team_id is not null

),

per_week as (

    -- A team can appear twice in one week in this data. Take the first game by id so the
    -- grain holds; a second fixture in the same week is rare enough that averaging two Elo
    -- readings would obscure more than it explains.
    select season, season_type, week, team_id, pregame_elo, postgame_elo
    from (
        select
            g.*,
            row_number() over (partition by season, season_type, week, team_id
                               order by game_id) as pick
        from team_games g
    ) ranked
    where pick = 1

),

joined as (

    select
        s.team_week_sk, s.season, s.season_type, s.season_type_ordinal, s.week, s.team_id,
        p.pregame_elo,
        p.postgame_elo,
        p.season is not null as has_game
    from spine s
    left join per_week p
        on  p.season      = s.season
        and p.season_type = s.season_type
        and p.week        = s.week
        and p.team_id     = s.team_id

),

grouped as (

    -- LAST NON-NULL WITHOUT `IGNORE NULLS`, which Postgres does not have — it is Oracle and
    -- Spark syntax and fails to parse here. The portable idiom is a running COUNT of the
    -- non-null values: it increments only when a reading appears, so every row sharing a
    -- count value sits in the same "since the last reading" group, and a plain max() over
    -- that group returns the reading. Works identically on both engines, so this stays one
    -- implementation rather than a dispatch.
    select
        j.*,
        count(postgame_elo) over (
            partition by season, team_id
            order by season_type_ordinal, week
            rows between unbounded preceding and current row) as reading_group
    from joined j

)

select
    team_week_sk,
    season,
    season_type,
    season_type_ordinal,
    week,
    team_id,
    has_game,
    pregame_elo,
    postgame_elo,
    -- The last rating actually observed at or before this week. A known value held constant,
    -- not an interpolation, and separate from the raw columns so a consumer chooses it
    -- deliberately. Null before a team's first reading of the season, which is correct: there
    -- is nothing to carry forward yet.
    max(postgame_elo) over (partition by season, team_id, reading_group)
                                                         as elo_carried_forward,
    -- TRUE where elo_carried_forward is holding an OLDER reading rather than this week's.
    -- Without it a step function and a measurement look identical on a chart.
    postgame_elo is null
        and max(postgame_elo) over (partition by season, team_id, reading_group) is not null
                                                         as elo_is_stale
from grouped
