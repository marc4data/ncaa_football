{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only` (R-226 pattern, B050). IT STRADDLES THE SCORES-DAG BOUNDARY:
-- fct_game IS in cfbd_scores_refresh's selector and fct_drive/srv_drive are NOT, so the
-- two-hourly run rebuilds one side of this comparison and tests it against a stale other side.
--
-- That is not a false alarm you can ignore. `publish_to_serving` sits downstream of `dbt_test`
-- on all_success, so a test failing for a reason the DAG cannot fix stops the serving database
-- being updated at all — the seventh instance of exactly this blocked the site for eight hours
-- on 2026-09-04. Full authority is kept on the weekly +tag:production build, which rebuilds
-- both sides.
--
-- Found by tests/test_dag_structure.py once there was a compiled manifest to read, which took
-- a warehouse connection. B046 wrote this test without one and could not have seen it.
-- Drives are `recent` scope: 2024 onward, measured from the raw manifest rather than assumed.
--
-- THE MIXED SAMPLE IS THE POINT. A test over 2025 games alone passes whether or not the
-- boundary is handled at all, so this asserts BOTH sides of it:
--
--   in scope      a completed game in a drive season has drives
--   out of scope  a game before the boundary has none, and the view still carries the bounds
--                 that let the page say why
--
-- The out-of-scope half is what stops "no drives" from being indistinguishable from "the join
-- broke". fct_game holds games back to the 1800s, so the outside case is well populated.
select 'a game before the drive scope boundary has drives' as failure
from {{ ref('srv_drive') }} d
where d.season < d.drives_min_season

union all

select 'srv_drive carries no scope bounds, so an empty game cannot explain itself'
from (
    select count(*) as n
    from {{ ref('srv_drive') }}
    where drives_min_season is null or drives_max_season is null
) probe
where probe.n > 0

union all

select 'no completed in-scope game has any drives'
from (
    select count(*) as n
    from {{ ref('fct_game') }} g
    where g.is_completed
      and g.season >= (select min(season) from {{ ref('fct_drive') }})
      and exists (select 1 from {{ ref('fct_drive') }} d where d.game_id = g.game_id)
) probe
where probe.n = 0
