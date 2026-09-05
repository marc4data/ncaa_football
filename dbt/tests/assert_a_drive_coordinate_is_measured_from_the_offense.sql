-- THE INVARIANT THE WHOLE DRIVE CHART RESTS ON.
--
-- stg_drive kept both `yardline` and `yards_to_goal` and declined to say which is "the" field
-- position. This test states the relationship between them, and it is exact:
--
--     is_home_offense = true    yardline + yards_to_goal = 100
--     is_home_offense = false   yardline = yards_to_goal
--
-- Measured over all 78,502 drives in the raw layer with ZERO exceptions. The 267 away-offense
-- drives satisfying both are at yardline 50, where the formulas coincide.
--
-- What it means: `yardline` is an absolute stadium coordinate in the HOME team's frame, and
-- `yards_to_goal` is offense-relative. That is why fct_drive draws the chart on
-- `100 - yards_to_goal` and never on `yardline` — on `yardline` the away band would MIRROR the
-- home band, and "align horizontally perfectly" would fail as what looks like a rendering bug.
--
-- IF THIS EVER FIRES, THE COORDINATE CHOICE IS WRONG AND EVERY BAR IN THE AWAY BAND IS
-- BACKWARDS. It is not a data-quality nicety; it is the assumption the geometry is built on.
select
    drive_id,
    game_id,
    drive_number,
    is_home_offense,
    start_yardline,
    start_yards_to_goal,
    start_yardline + start_yards_to_goal as start_sum
from {{ ref('fct_drive') }}
where start_yardline is not null
  and start_yards_to_goal is not null
  and case
        when is_home_offense then start_yardline + start_yards_to_goal <> 100
        else start_yardline <> start_yards_to_goal
      end
