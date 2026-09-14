{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` FOR THE SAME REASON ITS SIBLING IS — see
-- `assert_the_win_probability_curve_is_ordered_by_play_number`. The curve is on the WEEKLY
-- publish list and `metrics/wp` is fetched Sundays and Thursdays, so a two-hourly run has
-- nothing to re-check here and the blunt tag claims no coverage that does not exist.
--
-- R-770. `fct_game_win_probability_play.elapsed_from_kickoff_seconds` must be the TWIN of
-- `fct_drive.elapsed_from_kickoff_seconds` — same name, same units, same origin, same null rule
-- — because the whole point of the column is that the drives and the curve share ONE x-axis.
--
-- 🚨 WHAT THIS EXISTS TO CATCH IS AN ARITHMETIC THAT PRODUCES REAL NUMBERS ON A PLAUSIBLE AXIS.
-- `clock_seconds` means OPPOSITE THINGS in the two lineages, and that is measured, not feared:
--
--     stg_drive.start_clock_seconds   THE SECONDS COMPONENT of mm:ss  → fct_drive multiplies
--                                     the minutes and adds it
--     stg_play.clock_seconds          ALREADY THE TOTAL, minutes * 60 + seconds
--     stg_play.clock_seconds_part     the component
--
-- So copying `fct_drive`'s expression literally onto `stg_play`'s columns multiplies a total by
-- 60. Every row still computes, the column is still an integer, and every value is wrong.
--
-- ⚠️ A BOUND CANNOT SEE IT, AND THAT IS WHY THIS TEST RECOMPUTES INSTEAD OF BOUNDING. §6 mode 2
-- — an expression true by construction. `between 0 and 3600` is satisfied by a great many wrong
-- answers, and `is not null` by all of them.
--
-- ✅ SO THE FIRST CLAIM REBUILDS THE VALUE FROM THE COMPONENTS THE MART DOES NOT READ.
-- The mart reads the DERIVED total `clock_seconds`; this test reads `clock_minutes` and
-- `clock_seconds_part` and does the multiplication itself. That is an independent
-- recomputation across the exact seam the trap lives in, over every regulation row, rather
-- than a property of the output — so a 60x error disagrees on every play whose clock is not
-- exactly on the minute.
--
-- ✅ AND THE SECOND CLAIM PINS ONE NAMED PLAY BY HAND, because a recomputation shares a formula
-- with its subject and a hand-worked value shares nothing with it.
--
--     play 401856682175, Ohio State at Texas — period 1, 2:00 on the clock
--     three quarters of a quarter are gone: (1 - 1) * 900 + (900 - 120) = 780
--
-- ⚠️ THE ANCHOR'S CLOCK IS DELIBERATELY NOT 0:00, AND THIS IS THE SUBTLE PART. At 0:00 the 60x
-- break returns the CORRECT answer — 0 * 60 is still 0 — so an anchor at the end of a quarter
-- is a detector that cannot detect. The first three anchors worked by hand for this round were
-- all quarter-ends and all three would have passed the break. 120 * 60 = 7200 moves this one to
-- -6300.
--
-- ⚠️ THE ANCHOR IS SCOPED TO ITS GAME, AND THAT CONDITION IS DELIBERATE — CI CAUGHT THE FIRST
-- VERSION, WHICH WAS NOT. An unconditional `not exists` fired in CI and was RIGHT to: `ci/fixtures.sql`
-- is a small synthetic raw-layer load that does not carry game 401856682 and is not going to.
-- So the claim is conditional on the GAME being in the curve — if it is, the play must be there
-- and must read 780; if the game is absent, as in any fixture, the branch says nothing.
--
-- 🚨 AND A CONDITIONAL ASSERTION THAT NOBODY NAMES IS §6 MODE 2, so this names it: in CI this
-- branch is VACUOUS and only the recomputation above is doing any work. The anchor earns its
-- keep in the WAREHOUSE, which is where this round's verification happened and where the curve
-- actually lives. ⚠️ A missing game would go unnoticed HERE and loudly everywhere else — the
-- curve is 1,898 games and `assert_the_win_probability_curve_is_ordered_by_play_number` compares
-- every published play against its feed row.
--
-- ⚠️ REGULATION ONLY, and the boundary is the same one `fct_drive` draws and for the same
-- reason: college overtime has no game clock, so elapsed is undefined there and null BY DESIGN.
-- 787 of 291,548 rows. Asserting over them would be asserting that an invention is correct.
--
-- ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW — A097, A106 and A120 all paid for that
-- shape. This is a hash join on a unique key.
with recomputed as (

    select
        c.play_id,
        c.game_id,
        c.period,
        p.clock_minutes,
        p.clock_seconds_part,
        c.elapsed_from_kickoff_seconds                                        as published,
        -- ⚠️ FROM THE COMPONENTS, NOT FROM `p.clock_seconds`. Reading the derived total here
        -- would reproduce the model's own input and the test would agree with the break.
        (c.period - 1) * 900
            + (900 - (p.clock_minutes * 60 + p.clock_seconds_part))           as from_components
    from {{ ref('fct_game_win_probability_play') }} c
    join {{ ref('stg_play') }} p
      on p.play_id = c.play_id
    where c.period between 1 and 4
      and p.clock_minutes is not null
      and p.clock_seconds_part is not null

),

-- THE ANCHOR'S GAME, in one pass: how much of it is in the curve at all, and what the anchor
-- play reads if it is there. Scoping on the game is what makes the branch silent in a fixture
-- and load-bearing in the warehouse.
anchor_game as (

    select
        count(*)                                                            as rows_in_game,
        count(*) filter (where c.play_id = '401856682175')                   as anchor_rows,
        max(c.elapsed_from_kickoff_seconds)
            filter (where c.play_id = '401856682175')                        as anchor_elapsed
    from {{ ref('fct_game_win_probability_play') }} c
    where c.game_id = 401856682

)

select
    play_id,
    game_id,
    period,
    clock_minutes,
    clock_seconds_part,
    published,
    from_components as expected,
    'elapsed disagrees with the same clock rebuilt from its minutes and seconds components '
        || '— stg_play.clock_seconds is ALREADY a total and must not be multiplied' as rule
from recomputed
where published is distinct from from_components

union all

select
    '401856682175', 401856682::bigint, 1, 2, 0,
    anchor_elapsed,
    780,
    case
      when anchor_rows = 0
        then 'the anchor game is in the curve but the hand-checked play is not, '
             || 'so this branch can no longer detect anything'
      else 'the hand-checked anchor is wrong: period 1 at 2:00 is 780 seconds from kickoff'
    end
from anchor_game
where rows_in_game > 0
  and (anchor_rows = 0 or anchor_elapsed is distinct from 780)
