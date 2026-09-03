-- R-172/R-181. `upset_level` must not out-run its VERDICT.
--
-- The scale is drawn on the page as a mark, and a mark with no basis behind it is the defect
-- this test exists for. Two ways it can go wrong, both checked:
--
--   a level with no verdict   the row had nothing to judge by and was judged anyway. This is
--                             the null-propagation trap: `not null` is null rather than true,
--                             so without explicit branches a big win with no line falls
--                             through to the margin tests and comes out 'blowout'.
--   a verdict with no level   we had something to judge by and said nothing.
--
-- Rewritten twice as the definition moved: first when R-173 made the line the primary basis,
-- then when R-181 made it the only one and `upset_basis` was dropped. A test whose premise has
-- moved passes for the wrong reason, so it is repointed rather than left green.
select game_id, upset_level, is_upset_by_line, spread_at_close
from {{ ref('srv_game') }}
where is_completed
  and home_points is not null
  and ((is_upset_by_line is null and upset_level is not null)
    or (is_upset_by_line is not null and upset_level is null))
