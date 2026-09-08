-- The excursion must be a DIFFERENT MEASUREMENT from the net move, and this fails if it is not.
--
-- WHY THIS TEST EXISTS. `*_largest_excursion` and `*_move_from_open` are trivially equal on a
-- game whose line only ever moved one way, and a bug that made them equal EVERYWHERE — an
-- excursion that accidentally read the last snapshot instead of the widest — would look like
-- clean data. Every row would carry a plausible number and nothing would raise. A round trip is
-- invisible to net move and is exactly what a movement panel exists to show.
--
-- ⚠️ IT ASSERTS TWO THINGS, AND THE FIRST ONE IS THE SCALE-FREE ONE. A first draft required
-- "at least 50 games with a snapshot history", which is a production-shaped number written into
-- a test that also runs against a CI fixture holding one game — so it passed against the
-- warehouse and failed CI, which is the assertion having an opinion about the data volume
-- rather than about the data.
--
--   1. THE INVARIANT, on every row, everywhere: the widest departure from the open cannot be
--      NARROWER than the final one. |excursion| >= |move| is true by the definition of widest,
--      so a violation is a logic error and needs no population to detect.
--
--   2. THE DIVERGENCE, asked only where the data can answer it: if any game was observed at
--      more than three snapshots, then at least one such game must show excursion <> move.
--      Guarded by the data rather than by a constant, so it is strong against the warehouse
--      (1,577 of 1,854 games carry a single snapshot; among the 224 with real histories the two
--      differ on 17% of spreads and 29% of win probabilities) and silent where no game has a
--      history to diverge over.

with movement as (

    select * from {{ ref('fct_game_line_movement') }}

),

invariant_breaks as (

    select
        game_id,
        'excursion is narrower than the net move, which the widest departure cannot be'
            as failure
    from movement
    where (spread_move_from_open is not null and spread_largest_excursion is not null
           and abs(spread_largest_excursion) < abs(spread_move_from_open))
       or (total_move_from_open is not null and total_largest_excursion is not null
           and abs(total_largest_excursion) < abs(total_move_from_open))
       or (market_implied_win_probability_move_from_open is not null
           and market_implied_win_probability_largest_excursion is not null
           and abs(market_implied_win_probability_largest_excursion)
               < abs(market_implied_win_probability_move_from_open))

),

with_history as (

    select
        count(*)                                                       as games,
        count(*) filter (
            where spread_largest_excursion is distinct from spread_move_from_open
               or market_implied_win_probability_largest_excursion
                  is distinct from market_implied_win_probability_move_from_open
        )                                                              as diverging
    from movement
    where snapshot_count > 3

)

select game_id, failure from invariant_breaks

union all

select
    null::bigint,
    'no game with a snapshot history shows the excursion departing from the net move — '
    || 'the two columns are measuring the same thing'
from with_history
where games > 0 and diverging = 0
