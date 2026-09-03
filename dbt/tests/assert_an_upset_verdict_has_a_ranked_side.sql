-- R-172. AN UPSET NEEDS A FAVOURITE, AND A POLL RANK IS WHERE THIS MODEL GETS ONE.
--
-- `is_upset`'s `else false` branch used to fire when NEITHER team was ranked, so 91,047 of
-- 109,108 completed games asserted "not an upset" with nothing behind the claim. Marc found
-- it on the page: two Division II sides with no ranks and no line, drawn as an assessed
-- non-upset.
--
-- The property, stated so it cannot regress: a game may only carry a true-or-false verdict if
-- at least one side was ranked. No rank, no verdict.
select game_id, home_rank, away_rank, is_upset
from {{ ref('fct_game') }}
where is_upset is not null
  and home_rank is null
  and away_rank is null
