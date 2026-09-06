{{ config(severity='error') }}
-- Neither derivation of "favourite" may go missing when its inputs are present (R-393).
--
-- The defect this prevents is not a crash: it is a page ranking on `spread_favorite_side`
-- while its neighbour ranks on `moneyline_favorite_side`, with nothing recording that they
-- can differ. If either column silently stops being populated where it could be, one of the
-- three recap lists starts reading the other one's definition.
select game_id,
       coalesce(spread_at_close, spread_current) as spread_used,
       home_moneyline, away_moneyline,
       spread_favorite_side, moneyline_favorite_side
from {{ ref('fct_game_market') }}
where (coalesce(spread_at_close, spread_current) is not null
       and coalesce(spread_at_close, spread_current) <> 0
       and spread_favorite_side is null)
   or (home_moneyline is not null and away_moneyline is not null
       and home_moneyline <> away_moneyline
       and moneyline_favorite_side is null)
