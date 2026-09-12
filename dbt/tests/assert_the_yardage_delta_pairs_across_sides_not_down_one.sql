{{ config(severity='error') }}
-- R-686. 🚨 THE TRAP IS THAT THE TWO FIGURES LIVE ON DIFFERENT ROWS.
--
-- Marc, 2026-09-12: "Add a column that shows the delta. If the Team gained > allowed, then delta
-- value is positive."
--
-- The panel pairs THIS team's `_for` against THE OPPONENT'S `_allowed`. B's `_scatter` docstring
-- calls that pairing "the thing test_the_pairing_runs_across_sides_not_down_one was written first
-- to protect". So the delta is NOT `a - b` on one row: subtracting this team's own
-- `_for` minus its own `_allowed` gives a number that is plausible, differently wrong on every
-- row, and IDENTICAL to the correct one whenever the two teams happen to be similar — which is
-- why this test recomputes the pairing from the mart rather than checking the column for
-- self-consistency.
--
-- ⚠️ IT ASSERTS BOTH SIDES OF EVERY FIXTURE. A same-row subtraction also destroys a property the
-- correct pairing does not have: it makes the two sides of one game mirror images. Checking one
-- side would not see that.
with expected as (

    select
        t.game_id,
        t.team_id,
        round(ty.rushing_yards_for_per_game - oy.rushing_yards_allowed_per_game, 1) as rush,
        round(ty.passing_yards_for_per_game - oy.passing_yards_allowed_per_game, 1) as pass,
        round(ty.total_yards_for_per_game   - oy.total_yards_allowed_per_game,   1) as total,
        t.rushing_yards_for_minus_opponent_allowed_per_game as rush_col,
        t.passing_yards_for_minus_opponent_allowed_per_game as pass_col,
        t.total_yards_for_minus_opponent_allowed_per_game   as total_col
    from {{ ref('srv_game_team') }} t
    join {{ ref('fct_team_yardage_week') }} ty
      on  ty.season      = t.season
      and ty.season_type = t.season_type
      and ty.week        = t.week
      and ty.team_id     = t.team_id
    join {{ ref('fct_team_yardage_week') }} oy
      on  oy.season      = t.season
      and oy.season_type = t.season_type
      and oy.week        = t.week
      and oy.team_id     = t.opponent_team_id

)

select game_id, team_id, rush, rush_col, pass, pass_col, total, total_col,
       'this team FOR minus the OPPONENT allowed' as rule
from expected
where rush_col  is distinct from rush
   or pass_col  is distinct from pass
   or total_col is distinct from total
