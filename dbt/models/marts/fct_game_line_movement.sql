{{ config(materialized='table', tags=['market']) }}
-- HOW FAR THE LINE MOVED, AT GAME GRAIN. One row per game.
--
-- WHY THIS IS A MART PLUS COLUMNS ON srv_game, AND NOT A NEW SERVING VIEW.
--
-- srv_line_movement is SNAPSHOT grain — 27,623 rows over 3,378 games, measured 2026-09-08 —
-- and a panel wants one row per game. The app cannot do the aggregating: Streamlit is
-- display-only, single-table SELECT plus WHERE.
--
-- The grain rule (ratified 2026-09-02) says a view is named for its grain, and that anything
-- finer arrives "as its own view at its own grain, or as a DERIVED summary at game grain
-- computed in dbt and named so the derivation is visible". srv_game IS the game-grain view
-- and already carries spread_move_from_open, so a second game-grain serving view beside it is
-- precisely the four-views-over-one-fact defect the rule was written to stop. This mart is
-- the derived summary; srv_game surfaces its measures as columns.
--
-- ONE PROVIDER, AND THAT IS A FINDING RATHER THAN A PREFERENCE. See `line_movement_provider`
-- in dbt_project.yml: two books carry current snapshots and mixing them measures a move
-- against a different book's price, which is partly the spread between books rather than
-- anything the market did.
--
-- TWO MEASURES PER MARKET, AND THEY ARE NOT THE SAME NUMBER:
--
--   *_move_from_open        current minus open. Where it ended up.
--   *_largest_excursion     the widest departure from open at ANY snapshot in the game's
--                           life, signed, keeping the direction of that departure. Where it
--                           went on the way.
--
-- A059 measured excursion exceeding net move at every decile, and roughly a third of games
-- ending where they started having moved in between. A round trip is invisible to net move
-- and is exactly what a movement panel is for. assert_line_excursion_is_not_just_the_net_move
-- fails if the two columns ever agree everywhere, because a bug that made them identical
-- would otherwise look like clean data.
--
-- MONEYLINE MOVES IN DE-VIGGED PROBABILITY POINTS, NOT AMERICAN ODDS. -110 to -130 and +200
-- to +180 are not comparable as numbers; as probabilities they are 4.1 and 2.4 points. The
-- de-vig is fct_market_probability's, not a second one computed here, and only snapshots it
-- marks `is_probability_usable` are counted — a sentinel moneyline would otherwise register
-- as an enormous excursion.
--
-- NO THRESHOLDS. A059 measured the distributions and stopped there deliberately: "No
-- threshold proposed. Marc sets the line." What counts as a big move is not a modelling
-- decision and is not made here.

with snapshots as (

    select
        l.game_id,
        l.season,
        l.week,
        l.season_type,
        l.snapshot_ts,
        l.spread,
        l.spread_open,
        l.over_under,
        l.over_under_open
    from {{ ref('fct_betting_line') }} l
    where l.provider_key = '{{ var("line_movement_provider") }}'

),

probability as (

    -- The de-vigged home win probability per snapshot, in PROBABILITY POINTS (0..100) so the
    -- move reads in the same units the distribution was measured in.
    select
        p.game_id,
        p.snapshot_ts,
        p.market_implied_home_win_probability * 100 as home_win_probability_pct
    from {{ ref('fct_market_probability') }} p
    where p.provider_key = '{{ var("line_movement_provider") }}'
      and p.is_probability_usable

),

joined as (

    select
        s.*,
        pr.home_win_probability_pct
    from snapshots s
    left join probability pr
      on pr.game_id = s.game_id and pr.snapshot_ts = s.snapshot_ts

),

-- THE OPENING PROBABILITY IS THE FIRST USABLE ONE, NOT THE FIRST SNAPSHOT. fct_betting_line
-- carries an explicit spread_open and over_under_open; the moneyline has no such column, so
-- the open has to be taken from the earliest snapshot that actually has a usable probability.
opening_probability as (

    -- row_number() rather than `distinct on`: the latter is Postgres-only and this project
    -- dispatches the same models onto Databricks through one portability layer.
    select game_id, home_win_probability_pct as open_home_win_probability_pct
    from (
        select game_id, home_win_probability_pct,
               row_number() over (partition by game_id order by snapshot_ts) as seq
        from joined
        where home_win_probability_pct is not null
    ) ranked
    where seq = 1

),

latest as (

    select game_id, season, week, season_type, last_snapshot_ts,
           spread_current, total_current, current_home_win_probability_pct
    from (
        select game_id, season, week, season_type,
               snapshot_ts               as last_snapshot_ts,
               spread                    as spread_current,
               over_under                as total_current,
               home_win_probability_pct  as current_home_win_probability_pct,
               row_number() over (partition by game_id order by snapshot_ts desc) as seq
        from joined
    ) ranked
    where seq = 1

),

aggregated as (

    select
        j.game_id,

        min(j.snapshot_ts)                                   as first_snapshot_ts,
        count(*)                                             as snapshot_count,
        count(j.home_win_probability_pct)                    as usable_probability_snapshots,

        max(j.spread_open)                                   as spread_open,
        max(j.over_under_open)                               as total_open,

        -- THE EXCURSION IS THE SIGNED WIDEST DEPARTURE, not the widest absolute value dressed
        -- up as one. max(abs()) would lose the direction, and a line that went 3 points the
        -- wrong way is a different story from one that went 3 the right way.
        max(j.spread - j.spread_open) filter (where j.spread is not null
                                          and j.spread_open is not null) as spread_max_up,
        min(j.spread - j.spread_open) filter (where j.spread is not null
                                          and j.spread_open is not null) as spread_max_down,
        max(j.over_under - j.over_under_open) filter (where j.over_under is not null
                                          and j.over_under_open is not null) as total_max_up,
        min(j.over_under - j.over_under_open) filter (where j.over_under is not null
                                          and j.over_under_open is not null) as total_max_down
    from joined j
    group by j.game_id

)

select
    {{ surrogate_key(['a.game_id']) }}                       as game_line_movement_sk,
    a.game_id,
    l.season,
    l.week,
    l.season_type,

    '{{ var("line_movement_provider") }}'                    as provider_key,
    a.snapshot_count,
    a.usable_probability_snapshots,
    a.first_snapshot_ts,
    l.last_snapshot_ts,

    -- ---------------------------------------------------------------------------------------
    -- SPREAD
    -- ---------------------------------------------------------------------------------------
    a.spread_open,
    l.spread_current,
    case when l.spread_current is not null and a.spread_open is not null
         then l.spread_current - a.spread_open end           as spread_move_from_open,
    case when abs(coalesce(a.spread_max_up, 0)) >= abs(coalesce(a.spread_max_down, 0))
         then a.spread_max_up else a.spread_max_down end     as spread_largest_excursion,

    -- ---------------------------------------------------------------------------------------
    -- TOTAL
    -- ---------------------------------------------------------------------------------------
    a.total_open,
    l.total_current,
    case when l.total_current is not null and a.total_open is not null
         then l.total_current - a.total_open end             as total_move_from_open,
    case when abs(coalesce(a.total_max_up, 0)) >= abs(coalesce(a.total_max_down, 0))
         then a.total_max_up else a.total_max_down end       as total_largest_excursion,

    -- ---------------------------------------------------------------------------------------
    -- MONEYLINE, IN DE-VIGGED PROBABILITY POINTS. `market_implied_` because the prefix carries
    -- provenance: this is the book's price with the vig removed, never a prediction of ours.
    -- ---------------------------------------------------------------------------------------
    op.open_home_win_probability_pct                         as market_implied_home_win_probability_open,
    l.current_home_win_probability_pct                       as market_implied_home_win_probability_current,
    case when l.current_home_win_probability_pct is not null
          and op.open_home_win_probability_pct is not null
         then l.current_home_win_probability_pct - op.open_home_win_probability_pct
    end                                                      as market_implied_win_probability_move_from_open,
    ex.market_implied_win_probability_largest_excursion,

    -- ---------------------------------------------------------------------------------------
    -- ⚠️ THE CAVEAT TRAVELS ON THE ROW, because a caveat that cannot travel with the row does
    -- not survive to the page. True when this game's snapshot window SPANS the three days with
    -- no snapshots at all (see snapshot_gap_* in dbt_project.yml), which means its movement is
    -- measured ACROSS that hole and its excursion is a FLOOR rather than a measurement.
    --
    -- ⚠️ IT IS "SPANS", NOT "OPENED BEFORE", AND THE DIFFERENCE IS 1,630 WRONGLY FLAGGED ROWS.
    -- The first draft asked only whether the line opened before the gap, which is true of every
    -- 2024 and 2025 game — all of them opened, moved and finished a year before the outage and
    -- none was measured across anything. Measured: 1,728 rows flagged by the wrong test, 98 by
    -- the right one, and all 98 are in 2026 where the outage actually happened. A caveat that
    -- fires on 93% of rows indicates nothing, which is the same defect as an indicator that
    -- fires on all 34,061 colour rows.
    -- ---------------------------------------------------------------------------------------
    (a.first_snapshot_ts < timestamp '{{ var("snapshot_gap_start") }} 00:00:00+00'
     and l.last_snapshot_ts > timestamp '{{ var("snapshot_gap_end") }} 23:59:59+00')
                                                             as open_predates_snapshot_gap
from aggregated a
join latest l on l.game_id = a.game_id
left join opening_probability op on op.game_id = a.game_id
left join (
    -- The probability excursion needs the opening probability, which is a per-game value
    -- rather than a column on the snapshot, so it is computed after the join rather than in
    -- `aggregated`.
    select
        j.game_id,
        case when abs(coalesce(max(j.home_win_probability_pct - o.open_home_win_probability_pct), 0))
                  >= abs(coalesce(min(j.home_win_probability_pct - o.open_home_win_probability_pct), 0))
             then max(j.home_win_probability_pct - o.open_home_win_probability_pct)
             else min(j.home_win_probability_pct - o.open_home_win_probability_pct)
        end as market_implied_win_probability_largest_excursion
    from joined j
    join opening_probability o on o.game_id = j.game_id
    where j.home_win_probability_pct is not null
    group by j.game_id
) ex on ex.game_id = a.game_id
