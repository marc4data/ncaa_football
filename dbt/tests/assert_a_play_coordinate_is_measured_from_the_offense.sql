-- THE INVARIANT THE PLAY-LEVEL BORDER RESTS ON — the drive test's twin, one grain down.
--
-- A170 (cfdb-main-R-1325), for Marc's v19 ask: "borders around the yards gained by plays > 10
-- yards long". srv_player_play now publishes where a play STARTED and ENDED, and the geometry
-- is only safe while the relationship between the two frames holds:
--
--     offense = home_team    yardline + yards_to_goal = 100
--     offense = away_team    yardline = yards_to_goal
--
-- Measured over all 629,892 plays with ZERO exceptions — 317,520 home-offense and 312,372
-- away-offense — and the 8,140 satisfying both are at the 50, where the formulas coincide.
-- Re-measured at PLAY grain rather than inherited from fct_drive, because "it holds for drives"
-- is a claim about drives.
--
-- 🚨 IF THIS FIRES, EVERY PLAY SEGMENT IN THE AWAY BAND IS DRAWN BACKWARDS, and it will read as
-- a rendering fault while being a units fault. That is B133's mirrored-band defect, and it is
-- the specific thing A170's prompt got backwards: `yardline` is absolute in the HOME frame, so
-- a segment drawn on it MIRRORS. The chart is drawn on yards_from_own_goal for that reason.
--
-- ⚠️ ONE ROW IS EXCLUDED AND IT IS NOT A CARVE-OUT FOR THIS TEST. A play whose game is absent
-- from fct_game has no home_team to compare against, so the case expression has nothing to
-- decide — that is a coverage gap, which assert_play_stats_are_not_truncated_at_the_api_cap
-- and the scope boundary already speak to.
-- ⚠️ BOTH ENDS, AND THE SECOND HALF IS THE ONE THAT GUARDS A170's OWN CODE. The START
-- relationship is a fact about the SOURCE and would hold even if this round's case expression
-- were backwards; only the END half can fail when `end_yardline` picks the wrong branch. A
-- guard that cannot fail under the break it was written for is decoration (R-760), so this
-- one was checked by flipping the branch and watching it fire.
select 'start' as which_end, play_id, game_id, offense, home_team,
       yardline as yl, yards_to_goal as ytg, yardline + yards_to_goal as coordinate_sum
from {{ ref('fct_play') }}
where yardline is not null
  and yards_to_goal is not null
  and home_team is not null
  and case
        when offense = home_team then yardline + yards_to_goal <> 100
        else yardline <> yards_to_goal
      end

union all

select 'end' as which_end, play_id, game_id, offense, home_team,
       end_yardline, end_yards_to_goal, end_yardline + end_yards_to_goal
from {{ ref('fct_play') }}
where end_yardline is not null
  and end_yards_to_goal is not null
  and home_team is not null
  and case
        when offense = home_team then end_yardline + end_yards_to_goal <> 100
        else end_yardline <> end_yards_to_goal
      end
