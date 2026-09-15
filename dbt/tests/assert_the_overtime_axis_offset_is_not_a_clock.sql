-- A136, cfdb-main-R-904. `overtime_axis_offset_periods` is a POSITION ON A PLOT AXIS measured in
-- OVERTIME PERIODS. It is not a duration, it is not seconds, and it is not comparable with
-- `elapsed_from_kickoff_seconds`. This test asserts exactly those properties, because the way this
-- column goes wrong is that somebody later treats it as a clock.
--
-- 🚨 THE DECISION IT DEFENDS IS THE ONE `fct_drive` MADE FIRST AND A118 RATIFIED: an overtime
-- period is not 900 seconds of anything, so `(period - 1) * 900` would invent a duration that never
-- elapsed. The remedy is a SECOND coordinate in a DIFFERENT unit, not a wider definition of the
-- first — and the two must never both be populated on one play, or a chart could add them.
--
-- FIVE CLAIMS:
--
--   1. DISJOINT. No play carries both coordinates. Regulation has the clock; overtime has the
--      offset; the one play with no period at all has neither, which is AC-G.32 and not an
--      omission.
--   2. The offset is non-null exactly where the period is 5 or above.
--   3. floor(offset) + 1 = overtime_period. This is what makes the column readable as "which
--      overtime, and how far through it" rather than as an opaque number, and it is what lets a
--      chart put the reference line for overtime k at exactly k - 1.
--   4. The offset never leaves its own band: 0 <= offset and offset < overtime_period. A play
--      that escaped its band would be drawn inside the NEXT overtime, which is the drawing defect
--      this column exists to prevent.
--   5. The FIRST play of every overtime period sits exactly on the integer boundary. That is the
--      property the reference lines depend on; without it "each OT" has nowhere to draw.
--
-- ⚠️ CLAIM 5 IS THE ONE A STAGED BREAK CAN SEE AND THE OTHERS CANNOT. Changing the fraction from
-- (n - 1) / count to n / count keeps every value inside [0, period), keeps floor() intact for all
-- but the last play, and moves the whole band off its own reference line. Counts identical.
with p as (

    select
        game_id,
        play_id,
        period,
        elapsed_from_kickoff_seconds,
        overtime_period,
        overtime_axis_offset_periods                                          as offset_periods,
        min(overtime_axis_offset_periods) over (partition by game_id, period) as band_start
    from {{ ref('fct_game_win_probability_play') }}

)

select
    game_id,
    play_id,
    period,
    offset_periods::text  as offset_periods,
    case
        when elapsed_from_kickoff_seconds is not null and offset_periods is not null
            then 'a play cannot carry both a clock and an overtime axis offset'
        when period >= 5 and offset_periods is null
            then 'an overtime play must carry an overtime axis offset'
        when (period is null or period < 5) and offset_periods is not null
            then 'only overtime carries an overtime axis offset'
        when period >= 5 and floor(offset_periods) + 1 <> overtime_period
            then 'floor(offset) + 1 must be the overtime period'
        when period >= 5 and (offset_periods < 0 or offset_periods >= overtime_period)
            then 'the offset escaped its own overtime band'
        when period >= 5 and band_start <> overtime_period - 1
            then 'the first play of an overtime must sit exactly on its reference line'
    end as rule
from p
where (elapsed_from_kickoff_seconds is not null and offset_periods is not null)
   or (period >= 5 and offset_periods is null)
   or ((period is null or period < 5) and offset_periods is not null)
   or (period >= 5 and floor(offset_periods) + 1 <> overtime_period)
   or (period >= 5 and (offset_periods < 0 or offset_periods >= overtime_period))
   or (period >= 5 and band_start <> overtime_period - 1)
