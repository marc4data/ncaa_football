-- The arithmetic behind the convention, not just its sign.
--
-- The sign test above catches an inversion. This catches the subtler case: a margin that
-- happens to have the right sign but is not actually away-minus-home — a rounding change,
-- a points column swapped upstream, or a model exporting its own definition of margin.
select
    game_id,
    model_name,
    home_points,
    away_points,
    actual_margin,
    (away_points - home_points) as expected_margin
from {{ ref('fct_prediction') }}
where home_points is not null
  and away_points is not null
  and actual_margin is not null
  and abs(actual_margin - (away_points - home_points)) > 0.001
