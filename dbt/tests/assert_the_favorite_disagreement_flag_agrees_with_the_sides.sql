{{ config(severity='error') }}
-- The flag must say exactly what the two side columns say (R-393).
-- Catches the flag and the derivations drifting apart in a later edit -- the flag is what
-- the page will trust, and a flag that no longer matches its own inputs is worse than none.
select game_id, spread_favorite_side, moneyline_favorite_side, favorite_definitions_disagree
from {{ ref('fct_game_market') }}
where spread_favorite_side is not null
  and moneyline_favorite_side is not null
  and favorite_definitions_disagree
      is distinct from (spread_favorite_side is distinct from moneyline_favorite_side)
