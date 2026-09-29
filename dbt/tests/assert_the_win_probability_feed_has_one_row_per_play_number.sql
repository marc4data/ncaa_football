-- 🚨 ONE ROW PER (game, play_number) IN THE WIN-PROBABILITY FEED — A254 (cfdb-main-R-3576).
--
-- THIS IS THE GUARD THAT WOULD HAVE CAUGHT A253's 8-AGAINST-10 IN THE ROUND THAT CAUSED IT, and it
-- is written here rather than on the mart because the mart HIDES the defect: A183 gave
-- `fct_game_win_probability_play.play_number` a derived total ordinal, so a duplicate arriving from
-- staging is silently renumbered into two adjacent, legal-looking rows.
--
-- 📊 WHAT IT PINS, MEASURED. `stg_game_win_probability` used to dedup on `playId`, which CFBD
-- reissues and renumbers with. A re-fetched game therefore held every generation at once — 52
-- duplicate `(game_id, play_number)` groups across 24 games, all 2026 weeks 2-4. Because
-- `fct_game_win_probability_summary` orders its `lag()` windows on staging's `play_number`
-- (through `curve_order`), a duplicate makes that ordering NON-TOTAL, and the number of times the
-- curve crosses 0.5 then depends on which of two equal rows Postgres happens to return first.
-- Game 401861970 published 8 while the same rows recomputed to 10, and neither was a reading of
-- the football.
--
-- ⚠️ SO THIS ASSERTION IS THE PRECONDITION FOR `curve_order` BEING AN ORDER AT ALL. The ordering
-- lives in one macro and has several callers (A140); this is the property they all depend on, so
-- it is asserted once, here, at the source.
--
-- ✅ IT CAN FAIL, AND IT DID: against the pre-fix warehouse it returns 52 rows. A test that could
-- not go red under the defect it names is decoration (R-760, R-2254) — the staged break for this
-- one is simply the previous definition of the model it guards.
--
-- ⚠️ NOT A UNIQUENESS TEST ON `play_id`: that one already exists, through `staging_grains()`, and
-- it passed throughout — `play_id` was unique the entire time the feed was wrong. Two different
-- ids for one play is exactly the shape a play_id grain cannot see.

select
    game_id,
    play_number,
    count(*)                                  as rows_at_this_play_number,
    count(distinct play_id)                   as distinct_play_ids
from {{ ref('stg_game_win_probability') }}
group by game_id, play_number
having count(*) > 1
