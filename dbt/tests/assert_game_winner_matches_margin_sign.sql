-- The winner and the margin sign tell the same story, on every completed game.
--
-- cfdb stores margin as AWAY POINTS MINUS HOME POINTS, so a NEGATIVE margin means the HOME
-- team won. That is inverted from the intuitive reading and it is the single most dangerous
-- number in the project: a flip would invert every cover flag, every edge and every ATS
-- record while continuing to look entirely plausible.
--
-- It has been verified 3,402/3,402 in fct_prediction. This asserts the same thing where the
-- site actually reads it — srv_game, whose `winner` column is derived independently
-- from the points. Two derivations from the same source agreeing is worth more than one
-- derivation tested against itself.
--
-- Written because the Scores page used to re-derive the winner in Python from the sign of
-- actual_margin. It no longer does; it reads `winner`. This is what stops the convention
-- from becoming untested the moment the app stopped exercising it.
--
-- Non-FBS rows are NOT excluded. 11% of the scoreboard is a game against an opponent with
-- no dim_team row, and those are exactly the rows a name-based derivation gets wrong.
select
    game_id,
    season,
    home_team,
    away_team,
    home_points,
    away_points,
    actual_margin,
    winner
from {{ ref('srv_game') }}
where is_completed
  and home_points is not null
  and away_points is not null
  and (
      -- A home win is a negative margin, and the winner is the home team.
      (home_points > away_points and (actual_margin >= 0 or winner <> home_team))
      -- An away win is a positive margin, and the winner is the away team.
      or (away_points > home_points and (actual_margin <= 0 or winner <> away_team))
      -- A tie is a zero margin and has no winner. Distinct from an unplayed game, which
      -- this test does not reach because it filters on is_completed.
      or (home_points = away_points and (actual_margin <> 0 or winner is not null))
  )
