{{ config(severity='error') }}
-- The -100000 sentinel must never produce a win probability (R-391).
--
-- A TRIPWIRE, NOT A RESTATEMENT. stg_lines nulls the sentinel, so these rows are already
-- excluded by fct_market_probability's own `where`. This fails if that stops being true --
-- if the null is removed, if a second sentinel value appears, or if the `where` is relaxed.
-- Any of those puts a fabricated 0.98 win probability back at the top of the list that ranks
-- "the most surprising result of the week".
select game_id, provider_key, snapshot_ts, home_moneyline, away_moneyline
from {{ ref('fct_market_probability') }}
where has_moneyline_sentinel
