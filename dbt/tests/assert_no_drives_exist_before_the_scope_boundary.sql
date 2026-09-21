{{ config(tags=['scores_refresh_only']) }}
-- ⚠️ `scores_refresh_only`, NOT UNTAGGED — and the narrow tag is R-672's whole point.
-- `cfbd_scores_refresh` rebuilds `fct_drive` AND `fct_game` now, so it can satisfy this;
-- `cfbd_lines_snapshot` rebuilds `fct_game` alone and cannot. Removing the tag outright
-- blocked the LINES publish instead of the scores one — the blunt tag MOVES the failure
-- rather than fixing it, which is the mistake A105 made and this file's checker refuses.
-- 🚨 `full_refresh_only` REMOVED BY A185 (cfdb-main-R-1912). The tag means *no gated DAG
-- rebuilds both sides*, and that stopped being true the moment `cfbd_scores_refresh` began
-- fetching drives, plays and `metrics/wp` on the game-day cadence and building their models.
-- ⚠️ THE TAG WAS NOT REMOVED BY JUDGEMENT — `test_single_sided_tests_keep_their_coverage_in
-- _the_partial_rebuild_dags` FAILED and named this test, in its own words, as one whose tag
-- now *"costs real coverage"*. Leaving it would have shipped drives and the curve to the site
-- every two hours with their strongest guard switched off — which is the exact shape of
-- cfdb-main-R-1819, the defect this round's sibling closed.
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
