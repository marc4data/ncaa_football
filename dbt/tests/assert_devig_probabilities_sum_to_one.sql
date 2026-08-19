-- De-vigged probabilities must sum to exactly 1. That is the definition of removing the
-- vig, and it is the one property that distinguishes a de-vigged probability from a raw
-- implied one — which sums to ~1.05 and would silently overstate every edge computed
-- against it.
select
    betting_line_sk,
    game_id,
    market_implied_home_win_probability,
    market_implied_away_win_probability,
    market_implied_home_win_probability + market_implied_away_win_probability as total
from {{ ref('fct_market_probability') }}
where abs((market_implied_home_win_probability
           + market_implied_away_win_probability) - 1) > 0.0001
