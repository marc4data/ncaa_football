-- R-172/R-173. `upset_level` must not out-run its BASIS.
--
-- The scale is drawn on the page as a mark; a mark with no basis behind it is the defect this
-- pair of tests exists for. Two ways it can go wrong and both are checked:
--
--   a level with no basis   the row had nothing to judge by and was judged anyway. This is
--                           the null-propagation trap: `not null` is null rather than true,
--                           so before the explicit branches a big win with no line and no
--                           rank fell through to the margin tests and came out 'blowout'.
--   a basis with no level   we had something to judge by and said nothing.
--
-- Rewritten when R-173 made the LINE the primary basis: the earlier version compared
-- `upset_level` against `is_upset`, which is now only the RANK input to the verdict rather
-- than the verdict itself. A test whose premise has moved is a test that passes for the wrong
-- reason.
select game_id, upset_basis, upset_level, is_upset, is_upset_by_line
from {{ ref('srv_game') }}
where is_completed
  and home_points is not null
  and ((upset_basis is null and upset_level is not null)
    or (upset_basis is not null and upset_level is null))
