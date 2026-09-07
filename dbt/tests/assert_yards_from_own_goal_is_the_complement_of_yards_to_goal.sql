-- yards_from_own_goal = 100 - yards_to_goal, on both ends of every drive.
--
-- Trivial arithmetic, and worth a test precisely because it is: this is the one column both
-- bands of the chart are drawn on, so a typo in it is a silent geometry fault rather than an
-- error. The anchor case is a touchback — 75 yards to go, which must come out as 25 yards from
-- your own goal, and which is the single most common drive start in the data (20,393 of
-- 78,502). See its own test for that.
select
    drive_id,
    game_id,
    start_yards_to_goal,
    start_yards_from_own_goal,
    end_yards_to_goal,
    end_yards_from_own_goal
from {{ ref('fct_drive') }}
where (start_yards_to_goal is not null
        and start_yards_from_own_goal <> 100 - start_yards_to_goal)
   or (end_yards_to_goal is not null
        and end_yards_from_own_goal <> 100 - end_yards_to_goal)
