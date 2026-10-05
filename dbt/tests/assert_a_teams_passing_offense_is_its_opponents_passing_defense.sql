{{ config(tags=[]) }}

-- 🚨 THE OFFENSE/DEFENSE SIDES ARE RECONCILED, NOT TRUSTED (A286, cfdb-main-R-4892).
--
-- `teams.passing` arrived in CFBD v5.28-v5.32 and is the FIRST block in stg_game_box_team to
-- nest `offense` and `defense` sub-objects. Every other block is flat, so the model had no
-- precedent for assigning a side, and a wrong assignment here would read perfectly plausibly:
-- every column would be populated, every row present, every number in range.
--
-- ⚠️ THIS FILE'S SIBLING ALREADY LIVED THAT FAILURE. `stg_game_box_team`'s header records that
-- the `havoc` block lists the OPPOSITE team from `ppa` in 104 of 104 landed games — a
-- positional read would have attached every game's havoc numbers to the wrong team, silently
-- and universally. The direction of `havoc` is STILL unasserted there. This assertion is the
-- thing that section wishes it had.
--
-- THE INVARIANT: in a game, what a team THREW is what its opponent DEFENDED. So a team's
-- `passing_offense_attempts` must equal its opponent's `passing_defense_attempts`.
--
-- 📊 MEASURED BEFORE IT WAS ASSERTED (§2.4): 410 of 410 landed (game, team) pairs satisfy it,
-- with zero nulls on either side. It is an observed property of the feed, not a hope about it.
--
-- ⚠️ IT IS SCOPED TO ROWS THAT HAVE THE DATA, AND THAT IS NOT A WEAKENING. 205 of 2,239 games
-- carry these sections; the rest were fetched before CFBD served them and are NULL on both
-- sides. A null-tolerant comparison would pass vacuously on 2,034 games (§6's mode 2), so the
-- `is not null` bounds are what keep the assertion pointed at rows that can actually disagree.
--
-- 🚨 R-760's QUESTION, ANSWERED BY STAGING THE BREAK RATHER THAN BY REASONING — AND THE FIRST
-- ANSWER WAS "NOTHING". A286 swapped `offense` and `defense` for BOTH teams and this test
-- PASSED. The invariant is symmetric under a uniform swap: `a.offense == b.defense` and
-- `a.defense == b.offense` are one pair of equations, so flipping both sides everywhere maps
-- it onto itself. ⚠️ A reader who assumes this test pins the DIRECTION of the sides is wrong.
--
-- ✅ WHAT IT DOES CATCH IS AN ASYMMETRIC ERROR, measured: pointing `passing_defense_*` at the
-- offense sub-object — one side wrong, not both — fails it on 398 of 410 pairs. A join that
-- attached the wrong team's block is the same shape and the reason this matters, because the
-- `havoc` block in stg_game_box_team really is ordered opposite to `ppa` in 104 of 104 games.
--
-- 📋 PINNING THE ABSOLUTE DIRECTION needs an independent count of a team's pass attempts —
-- `stg_game_team_stat`, from /games/teams — which crosses the refresh boundary and needs the
-- tag machinery. cfdb-main-R-4893.

with sides as (

    select
        game_id,
        team,
        passing_offense_attempts,
        passing_defense_attempts
    from {{ ref('stg_game_box_team') }}
    where passing_offense_attempts is not null
      and passing_defense_attempts is not null

)

select
    a.game_id,
    a.team                     as team,
    b.team                     as opponent,
    a.passing_offense_attempts as team_threw,
    b.passing_defense_attempts as opponent_defended
from sides a
join sides b
    on b.game_id = a.game_id
   and b.team <> a.team
where a.passing_offense_attempts <> b.passing_defense_attempts
