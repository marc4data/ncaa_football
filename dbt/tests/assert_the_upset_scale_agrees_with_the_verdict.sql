-- R-172's other half: `upset_level` must not out-run `is_upset`.
--
-- `not null` is null rather than true, so before the explicit branch a big unranked win fell
-- through to the margin tests and would have been labelled an upset blowout. This is the
-- shape of that bug, asserted directly: a level on a game with no verdict, or no level on a
-- game that has one.
select game_id, is_upset, upset_level
from {{ ref('srv_game') }}
where is_completed
  and home_points is not null
  and ((is_upset is null and upset_level is not null)
    or (is_upset is not null and upset_level is null))
