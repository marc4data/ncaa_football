-- The excursion must be a DIFFERENT MEASUREMENT from the net move, and this fails if it is not.
--
-- WHY THIS TEST EXISTS. `*_largest_excursion` and `*_move_from_open` are trivially equal on a
-- game whose line only ever moved one way, and a bug that made them equal EVERYWHERE — an
-- excursion that accidentally read the last snapshot instead of the widest — would look like
-- clean data. Every row would carry a plausible number and nothing would raise. A059 measured
-- excursion exceeding net move at every decile and roughly a third of games ending where they
-- started having moved in between; a round trip is invisible to net move and is exactly what
-- a movement panel exists to show.
--
-- ⚠️ IT ASKS THE QUESTION ONLY OF GAMES THAT COULD ANSWER IT. 1,577 of 1,854 rows carry a
-- single snapshot — 2024 and 2025 were backfilled with one row per game — and on those the two
-- measures are equal BY CONSTRUCTION, not by defect. Asserting over all rows would make this
-- fail on correct data; asserting over none would make it vacuous. Among the 224 games with a
-- real snapshot history the two differ on 17% of spreads and 29% of win probabilities, so the
-- threshold below is far under what correct data produces and far over zero.
--
-- NOT TAGGED full_refresh_only, AND THE PROJECT'S OWN GUARD IS WHY. The tag was on it for one
-- draft; test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags rejected it —
-- "these are selected by the scores DAG and do not straddle the boundary, so the tag costs real
-- coverage". Correct: this test reads ONE model, so there is no fresh-side-against-stale-side to
-- protect against, and excluding it from the two-hourly run would simply stop it running. The
-- tag is for tests that span a refresh boundary, and applying it defensively is how coverage
-- disappears quietly.

with measurable as (

    select *
    from {{ ref('fct_game_line_movement') }}
    where snapshot_count > 3

),

counted as (

    select
        count(*)                                                       as games,
        count(*) filter (
            where spread_largest_excursion is distinct from spread_move_from_open
        )                                                              as spread_differs,
        count(*) filter (
            where market_implied_win_probability_largest_excursion
                  is distinct from market_implied_win_probability_move_from_open
        )                                                              as probability_differs
    from measurable

)

select
    games,
    spread_differs,
    probability_differs,
    'excursion never departs from the net move on any game with a snapshot history — '
    || 'the two columns are measuring the same thing'                  as failure
from counted
-- A scope with nothing in it cannot answer, and a test that passes on an empty scope is the
-- assertion this project has recorded three times.
where games < 50
   or spread_differs = 0
   or probability_differs = 0
