{{ config(severity='error', tags=['scores_refresh_only']) }}
-- 🚨 TAGGED `scores_refresh_only`, AND A GUARD SAID SO BEFORE A GAME DAY DID. R-684.
--
-- ci/check_test_refresh_scope.py, on this test's first run: it reads `fct_game_weather`, which
-- `cfbd_lines_snapshot` rebuilds, against `srv_game`, which it does not — so between the two
-- refreshes it would compare a fresh mart against a stale serving table, go red for a reason that
-- is not the defect, and stop the site publishing. That is R-672 exactly, which cost
-- `publish_distributions` four hours on a Friday.
--
-- ✅ `cfbd_scores_refresh` rebuilds BOTH sides, so the tag is the narrow one and no coverage is
-- lost: this test runs every two hours there, and the weekly `+tag:production` build keeps full
-- authority over it. The blunt `full_refresh_only` would have removed it from the scores DAG too,
-- which is the mistake A105 made first and had refused by this same guard.
-- R-684. THE DIRECTION LANDED ALL SEASON AND STOPPED IN STAGING.
--
-- stg_game_weather has parsed `windDirection` since the weather family shipped, and
-- fct_game_weather carries both the degrees and an 8-point compass point with a documented
-- rationale — and srv_game carried the SPEED and not the DIRECTION. Nothing was broken; a column
-- simply stopped one layer short of the only surface that reads it, and nothing said so.
--
-- ⚠️ THIS TEST DOES NOT RE-DERIVE THE COMPASS, ON PURPOSE. fct_game_weather owns the bucketing
-- and a second definition of north is exactly what §4.2 forbids and what A103 spent a round
-- undoing. It asserts CARRIAGE: what the page reads must equal what the mart holds.
--
-- It also fails if either column is deleted from srv_game, because this SQL would no longer
-- compile — which is the staged break for R-684.
select
    g.game_id,
    g.wind_direction_deg     as serving_deg,
    w.wind_direction_deg     as mart_deg,
    g.wind_direction_compass as serving_compass,
    w.wind_direction_compass as mart_compass
from {{ ref('srv_game') }} g
join {{ ref('fct_game_weather') }} w on w.game_id = g.game_id
where g.wind_direction_deg     is distinct from w.wind_direction_deg
   or g.wind_direction_compass is distinct from w.wind_direction_compass
