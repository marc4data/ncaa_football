{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` FOR THE SAME REASON AS ITS SIBLING, AND THE SIBLING'S HEADER
-- CARRIES THE MEASUREMENT. It reads `fct_player_leader_week`, which no gated DAG rebuilds — the
-- leader tables derive from player box scores and /games/players is fetched on Sundays and
-- Thursdays only. `ci/check_test_refresh_scope.py` is the guard that would otherwise stop a
-- publish, and R-672 is the round that found that class.
--
-- A116, R-717. `yards_per_carry_through_prior_week` is the one DERIVED column on the player cards:
-- §4.2 forbids the page dividing, so the model divides, and this test is what makes that division
-- checkable rather than merely asserted in a comment.
--
-- THREE CLAIMS, and each of them is a way the column has been got wrong in this project before:
--
--   1. WHERE THERE ARE CARRIES, the value is the accumulated yards over the accumulated carries,
--      rounded to one decimal. ⚠️ NOT the mean of the weekly averages. CFBD ships a per-game `AVG`
--      and a reader cannot tell the two apart by looking: 1 carry for 40 yards then 20 for 40 is
--      3.8 yards per carry, and averaging the weekly figures gives 22.0. Both are plausible on a
--      card and only one is true.
--   2. WHERE THERE ARE NO CARRIES, the value is NULL and never zero. AC-G.32 — "no carries" and
--      "zero yards per carry" are different facts, and a card printing 0.0 for a receiver who has
--      never run has invented a measurement rather than omitted one.
--   3. OUTSIDE THE RUSHING PANEL the column is null, because `carries_through_prior_week` is.
--      This is the clause that would catch a blanket `coalesce` being added to the model later —
--      the exact edit that would turn every receiver into a zero-yards-per-carry runner.
--
-- ⚠️ `round(numeric, 1)` IS RECOMPUTED HERE RATHER THAN COMPARED WITH A TOLERANCE. An epsilon
-- comparison would pass a column that rounds to two decimals, and the page renders whatever it is
-- given — so the rounding IS part of the contract, not an implementation detail.
select
    season, season_type, week, team_id, panel, player_id, player_name,
    yards_through_prior_week,
    carries_through_prior_week,
    yards_per_carry_through_prior_week as model_says,
    case when carries_through_prior_week > 0
         then round(yards_through_prior_week / carries_through_prior_week, 1)
    end as expected,
    case
      when panel <> 'rushing' and yards_per_carry_through_prior_week is not null
        then 'yards per carry outside the rushing panel'
      when coalesce(carries_through_prior_week, 0) = 0
           and yards_per_carry_through_prior_week is not null
        then 'no carries must read null, never zero'
      else 'yards per carry must divide the accumulated totals, rounded to one decimal'
    end as rule
from {{ ref('fct_player_leader_week') }}
where yards_per_carry_through_prior_week
      is distinct from case when carries_through_prior_week > 0
                            then round(yards_through_prior_week
                                       / carries_through_prior_week, 1)
                       end
   or (panel <> 'rushing' and yards_per_carry_through_prior_week is not null)
