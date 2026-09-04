-- THE TWO SIDES OF ONE BET CANNOT BOTH BEAT THE SPREAD.
--
-- `ats_margin = margin + team_spread`, and the two rows of a game hold exactly opposite
-- margins against exactly opposite spreads, so they must sum to zero. A pair that does not
-- cancel means the home/away sign was applied to only one of the two inputs — which produces
-- numbers in a believable range and a cover verdict that can say "yes" on both rows.
--
-- This is the check that the independent cross-check against srv_game.winner_covered_close
-- cannot make: that one grades the WINNER and would pass while the loser's row was wrong.
--
-- Zero violations across 3,287 games on 2026-09-04.
select
    game_id,
    sum(ats_margin_final) as ats_sum
from {{ ref('srv_game_team') }}
where ats_margin_final is not null
group by game_id
having abs(sum(ats_margin_final)) > 0.001
