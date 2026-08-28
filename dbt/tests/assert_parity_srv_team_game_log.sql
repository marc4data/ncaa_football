{{ config(tags=['parity']) }}
-- PARITY GATE: srv_team_game_log vs mart_team_schedule. See
-- assert_parity_srv_standings.sql for why EXCEPT rather than a join, for the scaffolding
-- note — this test is deleted when the mart it protects is dropped — and for the rule that
-- applies when it goes red:
--
--   WHEN PARITY FAILS, THE QUESTION IS WHICH SIDE IS RIGHT, never how to make them match.
--   Fixing the new side to agree with a defective old side turns a control into a liability.

with mart as (
    select
        cast(season as int)                               as season,
        cast(week as int)                                 as week,
        cast(season_type as {{ dbt.type_string() }})      as season_type,
        cast(game_id as int)                              as game_id,
        cast(team_id as int)                              as team_id,
        cast(team as {{ dbt.type_string() }})             as team,
        cast(conference as {{ dbt.type_string() }})       as conference,
        cast(classification as {{ dbt.type_string() }})   as classification,
        cast(opponent_id as int)                          as opponent_id,
        cast(opponent as {{ dbt.type_string() }})         as opponent,
        cast(opponent_conference as {{ dbt.type_string() }})     as opponent_conference,
        cast(opponent_classification as {{ dbt.type_string() }}) as opponent_classification,
        cast(game_date as date)                           as game_date,
        cast(kickoff_time_known as boolean)               as kickoff_time_known,
        cast(venue_role as {{ dbt.type_string() }})       as venue_role,
        cast(is_conference_game as boolean)               as is_conference_game,
        cast(is_neutral_site as boolean)                  as is_neutral_site,
        cast(venue as {{ dbt.type_string() }})            as venue,
        cast(attendance as int)                           as attendance,
        cast(is_completed as boolean)                     as is_completed,
        cast(points_for as int)                           as points_for,
        cast(points_against as int)                       as points_against,
        cast(result as {{ dbt.type_string() }})           as result,
        cast(margin as int)                               as margin
    from {{ ref('mart_team_schedule') }}
),

srv as (
    select
        cast(season as int)                               as season,
        cast(week as int)                                 as week,
        cast(season_type as {{ dbt.type_string() }})      as season_type,
        cast(game_id as int)                              as game_id,
        cast(team_id as int)                              as team_id,
        cast(team as {{ dbt.type_string() }})             as team,
        cast(conference as {{ dbt.type_string() }})       as conference,
        cast(classification as {{ dbt.type_string() }})   as classification,
        cast(opponent_id as int)                          as opponent_id,
        cast(opponent as {{ dbt.type_string() }})         as opponent,
        cast(opponent_conference as {{ dbt.type_string() }})     as opponent_conference,
        cast(opponent_classification as {{ dbt.type_string() }}) as opponent_classification,
        cast(game_date as date)                           as game_date,
        cast(kickoff_time_known as boolean)               as kickoff_time_known,
        cast(venue_role as {{ dbt.type_string() }})       as venue_role,
        cast(is_conference_game as boolean)               as is_conference_game,
        cast(is_neutral_site as boolean)                  as is_neutral_site,
        cast(venue as {{ dbt.type_string() }})            as venue,
        cast(attendance as int)                           as attendance,
        cast(is_completed as boolean)                     as is_completed,
        cast(points_for as int)                           as points_for,
        cast(points_against as int)                       as points_against,
        cast(result as {{ dbt.type_string() }})           as result,
        cast(margin as int)                               as margin
    from {{ ref('srv_team_game_log') }}
),

only_in_mart as (select * from mart except select * from srv),
only_in_srv  as (select * from srv  except select * from mart)

select 'missing_from_srv' as parity_issue, * from only_in_mart
union all
select 'extra_in_srv'     as parity_issue, * from only_in_srv
