-- Quarter-by-quarter points must add up to the final score. R-082.
--
-- The parse is arithmetic on a JSON array and arithmetic on the wrong index is silent: shift
-- by one and every game still renders four plausible quarters that happen to be wrong.
-- Summing them against a number the model did not derive is the check that cannot be fooled
-- that way. Overtime is included, which is what makes the 2021 Penn State - Illinois game
-- (nine overtimes, thirteen periods) a real test rather than a curiosity.
--
-- SEVERITY IS WARN, AND THE COUNT IS 53 OF 44,775 — 99.88% reconcile. Every failure is an
-- upstream one: CFBD publishes an all-zero line score beside a real final score, on small
-- Division II and III fixtures (Denison 0-0-0-0 against 28 points; Albright, Glenville State,
-- Mississippi Valley State the same shape). All are completed games, so this is not the
-- unplayed-game case. Nothing in this repo can fix it, and erroring would fail every build
-- over another organisation's data entry.
--
-- It earns its keep as a growth detector: 53 concentrated in small-school fixtures is the
-- known shape, and the same test reading several hundred, or naming an FBS programme, would
-- mean the parse itself had broken.
{{ config(severity='warn') }}

select
    game_id, season, home_team, away_team, home_periods,
    coalesce(home_q1, 0) + coalesce(home_q2, 0) + coalesce(home_q3, 0)
        + coalesce(home_q4, 0) + coalesce(home_overtime_points, 0) as line_score_total,
    home_points
from {{ ref('fct_game') }}
where home_periods is not null
  and coalesce(home_q1, 0) + coalesce(home_q2, 0) + coalesce(home_q3, 0)
      + coalesce(home_q4, 0) + coalesce(home_overtime_points, 0) <> home_points
