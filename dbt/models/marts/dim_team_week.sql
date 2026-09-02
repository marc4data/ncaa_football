{{ config(materialized='table') }}

-- The week calendar crossed with the teams in each season. One row per
-- (season, season_type, week, team_id). R-083 / R-084.
--
-- EXTRACTED SO THERE IS ONE SPINE, NOT TWO. fct_team_record_week built this inline, and
-- fct_team_rating_week needs exactly the same thing. A second spine that drifts from the
-- first is this project's signature defect — two implementations of one idea, agreeing until
-- they quietly do not — and prompt 030 removed two instances of it. Building a third would
-- have been an odd way to celebrate.
--
-- WALK THE CALENDAR, NOT THE GAMES. A team does not play every week. Building from a team's
-- games produces no row for a bye, and anything filtered to that week then renders an empty
-- cell rather than the state carried forward. That property is the whole reason this is a
-- spine and not a join.
--
-- SEASON TYPE ORDINAL, DERIVED FROM THE DATA'S OWN CHRONOLOGY, because postseason week
-- numbers restart at 1 and ordering on week alone puts a bowl game in the middle of October.
-- Four season types exist here, not two: within season 2020, `regular` runs Aug-Dec 2020,
-- `postseason` opens 2020-12-21, and the COVID-era `spring_regular` and `spring_postseason`
-- run Feb-May 2021.
--
-- EVERY TEAM IN fct_game, not just FBS. A Division II visitor appears on a schedule and needs
-- a row, or anything reading this renders inconsistently down the page.

with season_type_ordinal as (

    select * from (values
        ('regular', 1), ('postseason', 2), ('spring_regular', 3), ('spring_postseason', 4)
    ) as t(season_type, ordinal)

),

teams_in_season as (

    select distinct season, home_team_id as team_id from {{ ref('fct_game') }}
    where home_team_id is not null
    union
    select distinct season, away_team_id from {{ ref('fct_game') }}
    where away_team_id is not null

),

week_slots as (

    select distinct season, season_type, week from {{ ref('fct_game') }}

)

select
    {{ surrogate_key(['t.season', 'w.season_type', 'w.week', 't.team_id']) }} as team_week_sk,
    t.season,
    w.season_type,
    o.ordinal as season_type_ordinal,
    w.week,
    t.team_id
from teams_in_season t
join week_slots w on w.season = t.season
join season_type_ordinal o on o.season_type = w.season_type
