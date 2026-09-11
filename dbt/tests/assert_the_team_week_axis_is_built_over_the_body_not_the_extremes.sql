-- 🚨 R-641. THE AXIS MUST NOT BE BUILT OVER THE EXTREMES, AND THIS IS THE TEST THAT SAYS SO.
--
-- Marc, 2026-09-11: "The charts aren't correct. y-values are 0. That's not correct." He was
-- looking at Michigan's 106.0 rushing yards per game drawn 26 pixels off the floor of a
-- 150-pixel chart, because `rushing_yards_for_per_game` ran to 600 on the strength of four
-- triple-option academies while 103 of 282 teams — 36.5% — sat in the bottom fifth of the frame.
--
-- ⚠️ THE SQUASH IS WHAT THIS TEST NAMES. `floor`/`ceil` onto the step means the frame lands on a
-- labelled tick, so the honest invariant is a bounded one rather than an equality:
--
--     axis_max ∈ [whisker_high, whisker_high + axis_step)
--     axis_min ∈ (frame_low - axis_step, frame_low]      where frame_low = greatest(0, whisker_low)
--
-- Reverting the model to `ceil(max_value / axis_step) * axis_step` fails here the moment
-- max_value sits more than one step above whisker_high — which is precisely the condition that
-- squashes the chart, and exactly what `outlier_count > 0` reports. At 2026 regular week 2 that
-- is rushing_yards_for_per_game: whisker_high 365, axis_step 50, so an axis_max of 600 is 235
-- past the whisker and 185 past the tolerance.
--
-- ⚠️ IT IS NOT THE SAME ASSERTION AS "THE OUTLIERS ARE EXCLUDED". A frame may legitimately hold
-- every value — when outlier_count is 0 the whisker IS the maximum and the frame is unchanged —
-- so this test passes on an untightened axis and fails only on one built over a detached tail.
with f as (
    select season, season_type, week, metric,
           axis_min, axis_max, axis_step,
           whisker_low, whisker_high, min_value, max_value, outlier_count,
           greatest(cast(0 as {{ dbt.type_numeric() }}), whisker_low) as frame_low
    from {{ ref('fct_team_week_metric_distribution') }}
    where axis_step is not null
)
select *,
       axis_max - whisker_high as slack_above_the_whisker,
       frame_low - axis_min    as slack_below_the_frame
from f
where axis_max < whisker_high
   or axis_max >= whisker_high + axis_step
   or axis_min > frame_low
   or axis_min <= frame_low - axis_step
