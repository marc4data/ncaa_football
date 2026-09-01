-- `final_margin` and `total_points` must agree on what "no result" looks like.
--
-- srv_scoreboard's own comments argue at length that a game which has not been played must
-- read NULL rather than 0, citing ats_record_display shipping `0-0-0` for unplayed seasons
-- in the same row where wins and losses were correctly null. `final_margin` was doing
-- exactly that anyway: `abs(coalesce(home, 0) - coalesce(away, 0))` gave all 1,769 unplayed
-- games a margin of 0, which reads identically to a tie.
--
-- Asserted as agreement between the two columns rather than against is_completed alone,
-- because that is the property that actually matters: one row must not describe the same
-- absence two different ways.
select game_id, is_completed, home_points, away_points, final_margin, total_points
from {{ ref('srv_scoreboard') }}
where (final_margin is null) <> (total_points is null)
