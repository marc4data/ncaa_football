-- The pack's sign convention, pinned so that "fixing" it fails loudly.
--
--     actual_margin = away_points - home_points   ->   margin < 0 means the HOME team won
--
-- This is inverted from the intuitive reading, which is exactly why it needs a test: if
-- someone later normalises the margin to home-minus-away, every cover flag, every edge and
-- every ATS figure in the project flips sign — and every one of them still looks plausible.
-- Verified against all 5,133 rows of the pack's training data before it was adopted.
--
-- Only completed games are checked: an unplayed game has no points and no actual margin.
select
    game_id,
    model_name,
    home_points,
    away_points,
    actual_margin,
    'margin sign disagrees with the score' as failure
from {{ ref('fct_prediction') }}
where home_points is not null
  and away_points is not null
  and actual_margin is not null
  and (actual_margin < 0) <> (home_points > away_points)
  -- A tie is neither, and correctly satisfies neither side of the equality.
  and home_points <> away_points
