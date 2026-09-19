-- A177 (cfdb-main-R-1770). The opponent's record on one side of a game must BE the other
-- side's own record for the same game. Two rows, one fact, read from opposite directions.
--
-- 🚨 THIS IS THE TEST THAT CAN ACTUALLY FAIL, AND THAT IS WHY IT IS SHAPED THIS WAY. A null
-- check would pass on a join that matched the WRONG team — the column would be populated,
-- plausible, and wrong, which is the failure mode a new `_id` join key invites. `srv_game_team`
-- carries both sides of every game as separate rows, so the relation contains its own answer:
-- team A's `opponent_record_before_display` and team B's `record_before_display` are the same
-- string or the join is broken.
--
-- ⚠️ IT ALSO CATCHES THE OFF-BY-ONE. Both columns come from `fct_team_record_week`'s
-- leading-into frame; if one side were ever sourced from a record INCLUDING the game, the two
-- would disagree on exactly the games where it matters (R-285).
--
-- ⚠️ INNER JOIN, SO IT PINS WHAT IT CAN SEE AND IS SILENT WHERE THE OTHER SIDE IS ABSENT
-- (2.3.3). A game with one row in this relation — an FBS side against an opponent the
-- warehouse holds no team row for — is a different fact and not this test's business.
select
    a.game_id,
    a.team                            as side_a,
    a.opponent_record_before_display  as a_says_opponent_record_is,
    b.team                            as side_b,
    b.record_before_display           as b_says_its_own_record_is
from {{ ref('srv_game_team') }} a
join {{ ref('srv_game_team') }} b
  on  b.game_id = a.game_id
  and b.team_id = a.opponent_team_id
where a.opponent_record_before_display is distinct from b.record_before_display
