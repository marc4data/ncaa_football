{{ config(severity='error') }}
-- is_probability_usable must never be true where the inputs are not (R-391).
-- Catches the two flags drifting apart in a later edit.
select game_id, provider_key, snapshot_ts, overround, has_moneyline_sentinel
from {{ ref('fct_market_probability') }}
where is_probability_usable
  and (not is_overround_plausible or has_moneyline_sentinel)
