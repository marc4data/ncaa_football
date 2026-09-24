-- A214. EVERY RATE ON THE WEEK SUMMARY IS A SHARE, AND ITS NUMERATOR FITS INSIDE ITS
-- DENOMINATOR.
--
-- 🚨 THE RANGE CHECK ALONE WOULD BE HALF A TEST. `0 <= rate <= 1` passes on a rate computed
-- from the wrong denominator as long as the arithmetic happens to land inside the range — and
-- the whole point of publishing numerator, denominator and excluded count separately is that
-- they must AGREE. So this asserts the counts too.
--
-- ⚠️ IT `ref()`s ITS SUBJECT, WHICH IS NOT DECORATION (§3.6). A test that reads a catalogue
-- instead of the modelled relation is unordered with respect to it and can pass before the
-- thing it checks exists — `assert_serving_columns_are_documented` ran 24 seconds before
-- `srv_game` was created and was green.
--
-- ⚠️ AND A NULL RATE IS CORRECT, NOT A FAILURE. A week nobody has played has no favorite-win
-- rate; the model publishes null rather than 0.0 precisely so a bar is not drawn at the floor.
-- Every comparison below is therefore written so a null passes.
select
    season, season_type, week,
    favorite_straight_up_rate, favorite_straight_up_wins, favorite_straight_up_games,
    favorite_ats_rate, favorite_ats_covers, favorite_ats_games,
    over_rate, overs, over_under_decided_games,
    fbs_games, fbs_games_completed,
    undefeated_teams_lost, undefeated_teams_entering
from {{ ref('fct_week_summary') }}
where
    -- a rate outside [0, 1]
    favorite_straight_up_rate not between 0 and 1
 or favorite_ats_rate         not between 0 and 1
 or over_rate                 not between 0 and 1
    -- a numerator larger than its own denominator
 or favorite_straight_up_wins > favorite_straight_up_games
 or favorite_ats_covers       > favorite_ats_games
 or overs                     > over_under_decided_games
 or undefeated_teams_lost     > undefeated_teams_entering
 or fbs_games_completed       > fbs_games
    -- a rate published with no denominator behind it, or withheld when there is one
 or (favorite_straight_up_rate is null and favorite_straight_up_games > 0)
 or (favorite_straight_up_rate is not null and favorite_straight_up_games = 0)
 or (favorite_ats_rate is null and favorite_ats_games > 0)
 or (favorite_ats_rate is not null and favorite_ats_games = 0)
 or (over_rate is null and over_under_decided_games > 0)
 or (over_rate is not null and over_under_decided_games = 0)
    -- a count that cannot be negative
 or least(fbs_games, favorite_straight_up_pickems, favorite_ats_pushes,
          total_pushes, over_under_missing, undefeated_teams_lost) < 0
