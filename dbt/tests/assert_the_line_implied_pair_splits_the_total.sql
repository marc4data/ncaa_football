-- A GAME'S TWO LINE-IMPLIED SCORES MUST ADD UP TO THE OVER/UNDER.
--
-- R-201 verified this identity on 1,930 games before the pair was designed:
--     (total - spread)/2  +  (total + spread)/2  =  total
-- It is arithmetic, so it cannot drift on its own — but it CAN break if the team-perspective
-- sign flips on one side, if the two rows of a game ever draw their line from different
-- snapshots, or if a future edit reaches for abs() and loses the direction. Each of those
-- would leave every individual number looking plausible; only the pair gives it away.
--
-- Checked as a SUM over the game rather than per row for exactly that reason: a per-row test
-- would have to re-implement the formula to have something to compare against, and would
-- then agree with whatever the model does.
--
-- Zero violations across 3,287 games with a line on 2026-09-04.
select
    game_id,
    sum(line_implied_points_final) as implied_sum,
    max(total_final)               as total
from {{ ref('srv_game_team') }}
where line_implied_points_final is not null
group by game_id
having abs(sum(line_implied_points_final) - max(total_final)) > 0.001
