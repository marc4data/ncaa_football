-- R-173. THE SIGN CONVENTION, ASSERTED RATHER THAN TRUSTED.
--
-- Spread is the HOME number and negative means home favoured; margin is away minus home. Get
-- either backwards and the page calls every favourite's win an upset — a wrong answer that
-- looks entirely plausible, on the indicator a reader is least able to check.
--
-- Stated as the two things that must never be true:
--   a home favourite (spread < 0) who WON (margin < 0) flagged as an upset
--   an away favourite (spread > 0) who WON (margin > 0) flagged as an upset
select game_id, spread_at_close, actual_margin, is_upset_by_line
from {{ ref('srv_game') }}
where is_upset_by_line
  and ((spread_at_close < 0 and actual_margin < 0)
    or (spread_at_close > 0 and actual_margin > 0))
