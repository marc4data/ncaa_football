{{ config(severity='error') }}
-- ⚠️ NO `full_refresh_only` TAG, AND THE PROJECT'S OWN GUARD IS WHY. The first draft
-- carried it by habit from A151's roster test; `test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags`
-- refused it: this test reads ONE model, so it cannot straddle the two-hourly refresh
-- boundary, and tagging it would drop it from the scores DAG for nothing. **A tag that
-- buys no safety costs real coverage** (R-672's rule, read from the other side).
-- 🚨 MARC'S OWN DEFECT, ASSERTED — A152, cfdb-main-R-950.
--
-- *"Lead changes in 4th quarter doesn't seem accurate… Math isn't mathin'."* → *"Show actual
-- scoreboard lead changes instead."*
--
-- ⚠️ THE GAMES ARE NAMED AND THEIR NUMBERS WERE WORKED BY HAND FROM THE SCORING SEQUENCE, not
-- read back from the column this test checks (R-768: a test that re-derives a value from that
-- value proves only that the derivation is deterministic).
--
--     401858222  Richmond 0 at NC State 73, 2026 wk2   ->  0
--     401856661  Louisville 38 at Ole Miss 41, 2026 wk1 -> 5
--
-- 📊 THE FIRST IS THE CASE THAT MUST BE ZERO. A shutout: NC State scored first and the lead never
-- changed hands. Under the OLD column it is also 0, which is why the second anchor matters —
-- **an anchor that both definitions agree on cannot tell them apart** (R-843's rule: does the
-- pinned value MOVE under the thing you are testing).
--
-- 📊 THE SECOND IS THE ONE THAT SEPARATES THEM: hand-counted from the scoreboard it changes hands
-- five times, and the win-probability column publishes **16** for the same game. A game does not
-- change hands sixteen times.
--
-- ⚠️ AND 5 INCLUDES TWO THE FEED INVENTS, WHICH IS STATED RATHER THAN HIDDEN. At Q3 clock 394 the
-- feed stamps two plays from later in the game (play_id …890/…895) into an early slot, so the
-- scoreboard reads 13-18 → 16-17 → 27-24 → 16-17. **The hand count and the column agree at 5
-- because the hand count was taken from the same rows the model reads** — this test pins the
-- model against the SEQUENCE, not against a truth the warehouse does not hold. The model's own
-- header carries the exposure: 89 of 2,012 counted changes sit on such a row.
--
-- 🚨 R-760 — WHAT WOULD HAVE TO BE WRONG FOR THIS TO FIRE: swap the tie rule and Louisville goes
-- to 8; drop the carry-forward and it changes again; count from 0-0 and the shutout becomes 1.
-- Three different plausible mistakes, three different reds.
with expected (game_id, scoreboard_lead_changes, what) as (

    values
        (401858222, 0, 'Richmond 0 at NC State 73 — a shutout; the lead never changed hands'),
        (401856661, 5, 'Louisville 38 at Ole Miss 41 — hand-counted from the scoring sequence')

),

actual as (

    select game_id, scoreboard_lead_changes
    from {{ ref('fct_game_win_probability_summary') }}

)

select
    e.game_id,
    e.what,
    e.scoreboard_lead_changes as expected_count,
    a.scoreboard_lead_changes as published_count,
    case when a.game_id is null then 'the game is not in the summary at all'
         else 'the published count is not the hand-counted one' end as rule
from expected e
left join actual a on a.game_id = e.game_id
where a.game_id is null
   or a.scoreboard_lead_changes is distinct from e.scoreboard_lead_changes
