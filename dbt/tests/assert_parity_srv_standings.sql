{{ config(tags=['legacy_mart']) }}
-- TAGGED `legacy_mart`: excluded from cfbd_scores_refresh, which rebuilds one side of
-- this comparison and not the other. Full authority on the weekly +tag:production
-- build, which rebuilds both. See dags/scores_refresh_dag.py TEST_EXCLUDE.
-- PARITY GATE: srv_standings must be row-for-row identical to mart_team_season_record
-- before the site is repointed. This test is what converts the cutover from a calendar
-- decision into a proof.
--
-- EXCEPT rather than a join on the key: a join with `=` gives FALSE PASSES on nulls,
-- because `null = null` is unknown and the row is skipped. EXCEPT uses IS NOT DISTINCT FROM
-- semantics — nulls equal nulls, nulls differ from values — which is exactly what row
-- identity means. No coalesce: coalescing would mask a genuine null-vs-value difference.
--
-- EXCEPT is positional, so both sides project the same columns in the same order, listed
-- explicitly. Casts are explicit so int-vs-bigint or numeric scale differences do not read
-- as data differences. Columns srv_ adds beyond the mart are excluded — a column ADDED is
-- fine, a column MISSING fails.
--
-- A changed value produces TWO rows with the same key (one from each side), which is the
-- signature of a modified row rather than an added or dropped one.
--
--
-- WHEN PARITY FAILS, THE QUESTION IS WHICH SIDE IS RIGHT — never how to make them match.
--
--   New side wrong   fix the new side. The gate is doing its original job.
--   Old side wrong   fix the old side, or retire it. Record the divergence with its row
--                    count and reason as an EXPECTED DIVERGENCE. Never weaken the new side.
--   Both wrong       fix both, and the gate was never the point.
--
-- This is not hypothetical. srv_standings was fixed so that a team absent from dim_team
-- still carries a name, and this gate went red on 14,964 rows BECAUSE the serving view had
-- become more correct than the mart. Under a naive reading of "must be row-for-row
-- identical", the cheapest way to make that green is to re-introduce the bug on the new
-- side — which is a real temptation in a deadline week and would spend the credibility of
-- every other gate in the project.
--
-- A gate that can be silenced by making the new thing worse is worse than no gate.
-- This test is scaffolding: when mart_team_season_record is dropped it must be deleted in
-- the same commit. A parity test against a dropped model is a broken build; one kept
-- against a frozen copy asserts agreement with something no longer maintained.

with mart as (
    select
        cast(season as int)                                          as season,
        cast(team_id as int)                                         as team_id,
        cast(is_listed_team as boolean)                              as is_listed_team,
        cast(school as {{ dbt.type_string() }})                      as school,
        cast(conference as {{ dbt.type_string() }})                  as conference,
        cast(classification as {{ dbt.type_string() }})              as classification,
        cast(games_played as int)                                    as games_played,
        cast(wins as int)                                            as wins,
        cast(losses as int)                                          as losses,
        cast(ties as int)                                            as ties,
        cast(points_for as int)                                      as points_for,
        cast(points_against as int)                                  as points_against,
        cast(point_differential as int)                              as point_differential,
        cast(round(cast(win_pct as numeric), 3) as numeric(10, 3))   as win_pct
    from {{ ref('mart_team_season_record') }}
),

srv as (
    select
        cast(season as int)                                          as season,
        cast(team_id as int)                                         as team_id,
        cast(is_listed_team as boolean)                              as is_listed_team,
        cast(school as {{ dbt.type_string() }})                      as school,
        cast(conference as {{ dbt.type_string() }})                  as conference,
        cast(classification as {{ dbt.type_string() }})              as classification,
        cast(games_played as int)                                    as games_played,
        cast(wins as int)                                            as wins,
        cast(losses as int)                                          as losses,
        cast(ties as int)                                            as ties,
        cast(points_for as int)                                      as points_for,
        cast(points_against as int)                                  as points_against,
        cast(point_differential as int)                              as point_differential,
        cast(round(cast(win_pct as numeric), 3) as numeric(10, 3))   as win_pct
    from {{ ref('srv_standings') }}
),

only_in_mart as (select * from mart except select * from srv),
only_in_srv  as (select * from srv  except select * from mart)

select 'missing_from_srv' as parity_issue, * from only_in_mart
union all
select 'extra_in_srv'     as parity_issue, * from only_in_srv
