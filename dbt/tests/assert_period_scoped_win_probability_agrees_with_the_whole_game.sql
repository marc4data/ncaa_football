-- A117, R-709. The fourth-quarter measures are a SUBSET of the whole-game ones, and a subset
-- that disagrees with its parent is the defect this test exists to make impossible.
--
-- 🚨 THE REASON IT IS WORTH A TEST RATHER THAN A COMMENT: the period comes from a DIFFERENT MODEL.
-- `stg_game_win_probability` carries the curve and no period; `stg_play` carries the period. They
-- are joined on `play_id`, and a join that silently stopped matching — a feed changing its id
-- shape, a staging model narrowing its scope — would not error. It would quietly make every
-- period-scoped column read null or zero while the whole-game columns stayed perfectly correct.
-- That is A116's lesson one table over: a green build proves nothing about a column nothing checks.
--
-- FOUR CLAIMS:
--
--   1. A period's plays cannot outnumber the game's plays.
--   2. Fourth-quarter lead changes plus overtime lead changes cannot EXCEED the whole-game count.
--      ⚠️ They are not required to EQUAL it — periods 1 to 3 hold lead changes too — so this is an
--      inequality on purpose, and writing it as equality would fail on almost every real game.
--   3. A fourth-quarter swing cannot exceed the largest swing in the game.
--   4. NULL DISCIPLINE, and it is the claim most likely to rot: the period-scoped COUNTS are null
--      exactly when the feed never reached the fourth quarter, and populated exactly when it did.
--      Three games of 1,898 are in the first state. A later "tidy-up" coalescing them to zero
--      would claim we counted the fourth quarter of a game whose data stops in the third.
--
-- ── A155: REPOINTED ONTO `_by_clock`, BECAUSE THE FEED-ORDERED FIVE WERE CONTRACTED AWAY ─────
--
-- 🚨 THIS TEST WAS THE ONLY CONSUMER THE CONTRACT ROUND FOUND THAT WAS NOT A COMMENT, and it is
-- the reason a CONTRACT re-counts instead of trusting the round before it (§2.2.1c.1). Dropping
-- the five columns would have taken three of these four claims down with them — silently, since
-- a test that no longer compiles is a test nobody is watching.
--
-- ✅ THE INVARIANT IS A PROPERTY OF THE MEASURES, NOT OF ONE ORDERING, so it moves across intact.
-- 📊 VERIFIED ON ALL 1,898 ROWS BEFORE THE SWITCH rather than assumed: zero violations of claims
-- 2, 3 and 4 against the `_by_clock` family, and the null pattern is the SAME THREE GAMES — which
-- is what claim 4 is about, so a differing count would have been the thing to find.
select
    game_id,
    plays_with_win_probability,
    plays_with_win_probability_fourth_quarter   as q4_plays,
    plays_with_win_probability_overtime         as ot_plays,
    lead_changes_by_clock,
    lead_changes_fourth_quarter_by_clock        as q4_lead_changes,
    lead_changes_overtime_by_clock              as ot_lead_changes,
    largest_single_play_swing_by_clock,
    largest_single_play_swing_fourth_quarter_by_clock as q4_largest_swing,
    case
      when plays_with_win_probability_fourth_quarter
           + plays_with_win_probability_overtime > plays_with_win_probability
        then 'a period cannot hold more plays than the game'
      when coalesce(lead_changes_fourth_quarter_by_clock, 0)
           + coalesce(lead_changes_overtime_by_clock, 0)
           > lead_changes_by_clock
        then 'fourth quarter plus overtime lead changes exceed the whole game'
      when largest_single_play_swing_fourth_quarter_by_clock
           > largest_single_play_swing_by_clock
        then 'a fourth-quarter swing cannot exceed the largest swing in the game'
      when plays_with_win_probability_fourth_quarter = 0
           and lead_changes_fourth_quarter_by_clock is not null
        then 'no fourth-quarter plays must read null, never zero'
      when plays_with_win_probability_fourth_quarter > 0
           and lead_changes_fourth_quarter_by_clock is null
        then 'a fourth quarter that exists must carry a count'
    end as rule
from {{ ref('fct_game_win_probability_summary') }}
where plays_with_win_probability_fourth_quarter
      + plays_with_win_probability_overtime > plays_with_win_probability
   or coalesce(lead_changes_fourth_quarter_by_clock, 0)
           + coalesce(lead_changes_overtime_by_clock, 0)
      > lead_changes_by_clock
   or largest_single_play_swing_fourth_quarter_by_clock
      > largest_single_play_swing_by_clock
   or (plays_with_win_probability_fourth_quarter = 0
       and lead_changes_fourth_quarter_by_clock is not null)
   or (plays_with_win_probability_fourth_quarter > 0
       and lead_changes_fourth_quarter_by_clock is null)
