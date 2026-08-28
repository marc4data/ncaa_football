{{ config(materialized='table') }}

-- One row per game, across every season landed in raw.
--
-- MATERIALIZED AS A TABLE, and alone among the staging models in that. Staging is views by
-- convention because a view costs nothing to build and the work is trivial. This model
-- stopped being trivial when the game_id dedup below was added: a window function is an
-- optimization fence, and this view is referenced FOUR times — twice inside fct_game alone,
-- once for a GROUP BY and once joined to four other relations. As a view each reference is
-- re-inlined and re-sorted, and the planner, unable to push predicates through the fence,
-- chose a plan for fct_game that had not finished after eight minutes against a build that
-- previously took under thirty seconds for the whole 27-model selection.
--
-- Reading the view standalone is 216 ms. The cost was never the dedup; it was paying for it
-- once per reference and denying the planner any statistics. As a table the dedup runs once
-- per dbt run and every downstream model reads an analyzed relation.
--
-- DEDUP HAPPENS TWICE, ON TWO DIFFERENT KEYS, BECAUSE THERE ARE TWO DIFFERENT DUPLICATES.
--
-- 1. Per params, keeping the newest FILE. The backfill fetches each season twice — once for
--    `seasonType=regular`, once for `postseason` — so deduping per season would silently
--    discard the bowl games. Keying on the whole params object generalises: one surviving
--    file per distinct request, whatever dimensions that request had.
--
-- 2. Per game_id, keeping the row from the newest file. Step 1 is only sufficient while
--    requests are DISJOINT, and it has no answer for OVERLAPPING ones. cfbd_scores_refresh
--    fetches `{year, week, seasonType}`; the backfill holds `{year, seasonType}` for the
--    whole season. Different params, so different partitions, so both files survive step 1
--    — and every game the week-scoped file shares with the season-wide one is emitted
--    twice. That is 211 duplicate game_ids on the first live run of the scores DAG, and
--    nine failing tests: the unique tests on stg_games and fct_game, the schedule
--    reconciliation assertions, and srv_team_game_log parity.
--
--    It had never fired because nothing in the project fetched a single week until the
--    scores DAG did. Two latent faults that only meet on first use.
--
--    Newest file wins, matching step 1, so a refetch supersedes rather than races: the
--    2-hourly scores fetch is by construction newer than the backfill it overlaps.
--
-- Verified as a strict no-op for history: across 157 seasons of raw, 1869 to 2025, this
-- drops zero rows. Only 2026 changes, and only by the 211 it is here to remove.
--
-- JSON access goes through the dispatched macros (see macros/json.sql); the dedup uses a
-- window function rather than Postgres' `distinct on`, which Spark has no equivalent for.

with successful_fetches as (

    select
        params,
        filename,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (
            partition by params
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_games') }}
    where status_code = 200

),

exploded as (

    select
        filename,
        {{ json_array_elements('payload') }} as game
    from successful_fetches
    where recency = 1

),

games as (

    select game
    from (
        select
            game,
            row_number() over (
                partition by cast({{ json_get_string('game', 'id') }} as int)
                order by filename desc
            ) as game_recency
        from exploded
    ) ranked
    where game_recency = 1

)

select
    cast({{ json_get_string('game', 'id') }} as int)              as game_id,
    cast({{ json_get_string('game', 'season') }} as int)          as season,
    cast({{ json_get_string('game', 'week') }} as int)            as week,
    {{ json_get_string('game', 'seasonType') }}                   as season_type,
    cast({{ json_get_string('game', 'startDate') }} as {{ type_timestamp_tz() }}) as start_date,
    cast({{ json_get_string('game', 'completed') }} as boolean)   as is_completed,
    cast({{ json_get_string('game', 'conferenceGame') }} as boolean) as is_conference_game,
    cast({{ json_get_string('game', 'neutralSite') }} as boolean) as is_neutral_site,
    cast({{ json_get_string('game', 'homeId') }} as int)          as home_team_id,
    {{ json_get_string('game', 'homeTeam') }}                     as home_team,
    cast({{ json_get_string('game', 'homePoints') }} as int)      as home_points,
    {{ json_get_string('game', 'homeClassification') }}           as home_classification,
    cast({{ json_get_string('game', 'awayId') }} as int)          as away_team_id,
    {{ json_get_string('game', 'awayTeam') }}                     as away_team,
    cast({{ json_get_string('game', 'awayPoints') }} as int)      as away_points,
    {{ json_get_string('game', 'awayClassification') }}           as away_classification,
    {{ json_get_string('game', 'venue') }}                        as venue,
    cast({{ json_get_string('game', 'attendance') }} as int)      as attendance,
    {{ safe_numeric(json_get_string('game', 'excitementIndex')) }} as excitement_index
from games
