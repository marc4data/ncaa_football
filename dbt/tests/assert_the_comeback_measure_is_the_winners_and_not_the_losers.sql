-- A136, cfdb-main-R-903. `winner_mean_win_probability` is the EVENTUAL WINNER's mean win
-- probability, and this test exists because the obvious break is invisible to every count.
--
-- 🚨 THE BREAK IT IS BUILT AGAINST: swap the two arms of the `case`, so the column publishes the
-- LOSER's mean instead. Row count identical. Null count identical. Min, max, distinct count and
-- data type identical — x becomes 1 - x, which is still a probability in [0, 1]. Every "the panel
-- has rows" assertion passes. The ONLY thing that changes is which team the number is about, and
-- every game reorders. R-852: the guard has to see the thing the counts cannot.
--
-- 🚨 AND THE SYMMETRY IS WHY THE NAIVE TEST FAILS. "The winner's mean plus the loser's mean is 1"
-- holds in BOTH directions, so any assertion built on that identity passes under the swap. So does
-- "the value lies between the lowest and highest win probability", because a mean of 1 - x lies
-- between 1 - max and 1 - min. ⚠️ THE ONLY THING THAT BREAKS THE SYMMETRY IS THE IDENTITY OF THE
-- WINNER, so the test must fetch it from somewhere the model did not.
--
-- ✅ SO IT REACHES OUTSIDE THE MODEL'S OWN INPUTS, TWICE OVER — A135's shape:
--
--     who won      `fct_game_team`, the BOX SCORE — one row per side, each carrying its OWN
--                  points_for. The model asks `fct_game.home_points > away_points`. Different
--                  relation, different grain, and a swap in either shows up here.
--     who is home  `fct_game_team.is_home`, from the same box score rather than from the
--                  schedule row the model read.
--
-- ⚠️ THE FIRST DRAFT TOOK `home_team_id` FROM `fct_game_win_probability_play` INSTEAD, AND
-- `test_every_test_the_scores_dag_cannot_satisfy_is_tagged` REFUSED IT — correctly. The scores
-- DAG refreshes `fct_game_team` and this summary but NOT the play-grain curve, so that version
-- compared two relations with different fetch times and would have measured the gap between
-- them. ✅ Nothing was lost by moving: the curve's `home_team_id` agrees with `fct_game` on
-- 1,898 of 1,898 games, so it was never going to catch anything the box score cannot.
--
-- ⚠️ CLAIM 3 IS A VALUE ANCHOR AND IT IS CHOSEN SO THE BREAK MOVES IT (R-843). Ohio State @ Texas,
-- 2026 week 2, is the game Marc named and the lowest winner mean of that week at 0.2291; under the
-- swap it publishes 0.7709. A game near 0.5 would have passed the break — 1 - x is only close to x
-- where x is close to a half — and an anchor sitting on an identity element is the failure R-843
-- was written for. It is also drawn FROM the population under test rather than from beside it.
--
-- ⚠️ CLAIM 4 IS THE POPULATION SHAPE, and it is here because claims 1 to 3 all depend on joins
-- that could themselves stop matching. Favorites usually win, so the winner's mean is above 0.5
-- far more often than below: measured 1,653 games against 245. Under the swap those two numbers
-- exchange places. It is one row of assertion and it cannot be satisfied by an empty result,
-- because the aggregate is computed over the whole model.
with box as (

    select
        game_id,
        max(team_id) filter (where points_for > points_against) as winning_team_id,
        max(team_id) filter (where is_home)                     as home_team_id,
        count(*)                                                as sides
    from {{ ref('fct_game_team') }}
    group by game_id

),

per_game as (

    select
        s.game_id,
        s.mean_home_win_probability,
        s.winner_mean_win_probability,
        b.winning_team_id,
        b.home_team_id,
        case
            when b.winning_team_id is null or b.home_team_id is null then null
            when b.winning_team_id = b.home_team_id then s.mean_home_win_probability
            else round(1 - s.mean_home_win_probability, 4)
        end                                                     as expected_from_the_box_score
    from {{ ref('fct_game_win_probability_summary') }} s
    left join box b on b.game_id = s.game_id and b.sides = 2

),

shape as (

    select
        count(*) filter (where winner_mean_win_probability > 0.5) as above_even,
        count(*) filter (where winner_mean_win_probability < 0.5) as below_even
    from per_game

)

-- CLAIM 1 — the arm the model took agrees with the box score and the curve's own home team.
select
    game_id,
    winner_mean_win_probability::text                            as published,
    expected_from_the_box_score::text                            as expected,
    'the published winner mean is the OTHER side of the game'    as rule
from per_game
where expected_from_the_box_score is not null
  and winner_mean_win_probability is distinct from expected_from_the_box_score

union all

-- CLAIM 2 — every game with a curve and a two-sided box score carries the measure.
select
    game_id,
    coalesce(winner_mean_win_probability::text, 'null'),
    'a value',
    'a game with a curve and a decided box score must carry a winner mean'
from per_game
where winning_team_id is not null
  and winner_mean_win_probability is null

union all

-- CLAIM 3 — the anchor. Ohio State @ Texas, 2026 week 2: 0.2291 published, 0.7709 under the swap.
select
    game_id,
    winner_mean_win_probability::text,
    'below 0.35',
    'the anchor game moved: Texas trailed almost throughout and won'
from per_game
where game_id = 401856682
  and (winner_mean_win_probability is null or winner_mean_win_probability >= 0.35)

union all

-- CLAIM 4 — the population shape. 1,653 above even against 245 below, measured 2026-09-15.
select
    0,
    above_even::text,
    below_even::text,
    'winners are usually favorites: above-even must outnumber below-even'
from shape
where above_even <= below_even
