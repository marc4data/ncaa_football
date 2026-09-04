-- A NEGATIVE LINE-IMPLIED SCORE IS IMPOSSIBLE AND WOULD MEAN abs(spread) > total.
--
-- R-201 asked for this test by name: "its first appearance is bad line data, and it would be
-- invisible in the aggregate." A distribution built over these values would simply shift, and
-- the weekly favourite/underdog gap — the whole reason the metric exists — would move for a
-- reason that has nothing to do with football.
--
-- Lowest observed on 2026-09-04 is 2.5, across every season the market covers.
select game_team_sk, spread_final, total_final,
       line_implied_points_final, line_implied_points_open
from {{ ref('srv_game_team') }}
where line_implied_points_final < 0
   or line_implied_points_open  < 0
