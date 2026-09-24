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
-- 🚨 AND THE THIRD THING IT ASSERTS IS THE ONE A214'S STAGED BREAKS FORCED IT TO GROW: THE
-- COUNTS MUST PARTITION THE POPULATION, NOT MERELY FIT INSIDE IT.
--
-- 📊 MEASURED, on 2026 regular week 3. Counting a push as a cover takes `favorite_ats_covers`
-- from 35 to 36 against a denominator of 74. `covers <= games` is still true. Every rate is
-- still inside [0, 1]. **Both halves of this test as originally written stayed green on a
-- staged break that was plainly wrong** — R-2260's class, in a test written to avoid it.
--
-- ✅ THE ONLY THING THAT SEES IT IS AN IDENTITY: the states are mutually exclusive and cover
-- every completed game, so their counts must SUM to the population. That is why
-- `favorite_ats_fails` and `unders` are published at all — a partition cannot be asserted from
-- one side of it. 📊 Week 3: 35 + 39 = 74 covers+fails=games, and 74 + 1 push + 0 no-line +
-- 0 pick'ems = 75 = completed games. Under the break the first identity reads 36 + 39 = 75
-- against a denominator of 74 and the row fires.
select
    season, season_type, week,
    favorite_straight_up_rate, favorite_straight_up_wins, favorite_straight_up_games,
    favorite_ats_rate, favorite_ats_covers, favorite_ats_fails, favorite_ats_games,
    favorite_ats_pushes, favorite_ats_no_line, favorite_straight_up_pickems,
    favorite_straight_up_no_line, over_rate, overs, unders, over_under_decided_games,
    total_pushes, total_no_line,
    fbs_games, fbs_games_completed,
    undefeated_teams_lost, undefeated_teams_entering
from {{ ref('srv_week_summary') }}
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
    -- 🚨 THE PARTITIONS. Each set of states is mutually exclusive and exhaustive over the
    -- population named on the right, so these are equalities rather than bounds. A bound is
    -- what let a push count as a cover and stay green.
 or favorite_ats_covers + favorite_ats_fails <> favorite_ats_games
 or overs + unders <> over_under_decided_games
 or favorite_ats_games + favorite_ats_pushes + favorite_ats_no_line
        + favorite_straight_up_pickems <> fbs_games_completed
 or favorite_straight_up_games + favorite_straight_up_pickems
        + favorite_straight_up_no_line <> fbs_games_completed
 or over_under_decided_games + total_pushes + total_no_line <> fbs_games_completed
