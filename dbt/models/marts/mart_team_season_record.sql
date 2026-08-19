{{ config(materialized='table', tags=['production']) }}

-- One row per team per season: win/loss record and scoring, from completed games only.
--
-- Games are stored one row per matchup; a team-level record needs each game counted
-- once from each side, so unpivot home/away into one row per team-game first.
--
-- Team attributes join on **(season, team_id)**, not team_id alone — see stg_teams for
-- why. That join is deliberately a LEFT join: CFBD's season team list covers FBS and FCS,
-- but schedules include lower-division opponents, so some team-seasons have no listed
-- attributes. Dropping those rows would break the league-wide invariant that every game
-- produces one win and one loss (the reconciliation test below depends on it), so they
-- are kept and flagged with `is_listed_team` instead. Consumers filter; the mart doesn't
-- silently discard.

with team_games as (

    select
        season,
        home_team_id as team_id,
        home_points  as points_for,
        away_points  as points_against
    from {{ ref('stg_games') }}
    where is_completed
      and home_points is not null
      and away_points is not null

    union all

    select
        season,
        away_team_id as team_id,
        away_points  as points_for,
        home_points  as points_against
    from {{ ref('stg_games') }}
    where is_completed
      and home_points is not null
      and away_points is not null

),

aggregated as (

    select
        season,
        team_id,
        count(*)                                                          as games_played,
        count(case when points_for > points_against then 1 end)           as wins,
        count(case when points_for < points_against then 1 end)           as losses,
        count(case when points_for = points_against then 1 end)           as ties,
        sum(points_for)                                       as points_for,
        sum(points_against)                                   as points_against
    from team_games
    group by season, team_id

)

select
    cast(a.season as {{ dbt.type_string() }}) || '-' || cast(a.team_id as {{ dbt.type_string() }}) as team_season_key,
    a.season,
    a.team_id,
    t.team_id is not null as is_listed_team,
    t.school,
    t.conference,
    t.classification,
    a.games_played,
    a.wins,
    a.losses,
    a.ties,
    a.points_for,
    a.points_against,
    a.points_for - a.points_against as point_differential,
    round(cast(a.wins as numeric) / nullif(a.games_played, 0), 3) as win_pct
from aggregated a
left join {{ ref('stg_teams') }} t
    on t.team_id = a.team_id
   and t.season = a.season
