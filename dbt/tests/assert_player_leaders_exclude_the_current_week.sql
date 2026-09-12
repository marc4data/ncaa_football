{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only`, AND A GUARD SAID SO BEFORE A GAME DAY DID. R-687.
--
-- ci/check_test_refresh_scope.py, on this test's first run: it reads `dim_team_week`, which
-- `cfbd_scores_refresh` rebuilds, against `fct_player_leader_week` and `fct_player_yardage_week`,
-- which it does not — so it would compare a fresh spine against stale leaders and stop that DAG's
-- publish. That is R-672 exactly.
--
-- ⚠️ AND HERE THE BLUNT TAG IS THE CORRECT ONE, WHICH IS THE OPPOSITE OF THE TWO MARKET TESTS
-- ABOVE. NO gated DAG rebuilds both sides: the leader tables are derived from player box scores,
-- and /games/players is fetched only on Sundays and Thursdays, so they move weekly by
-- construction. `scores_refresh_only` would claim a coverage that does not exist. Nothing real is
-- lost — the weekly `+tag:production` build runs this at exactly the cadence the data changes.
-- R-687. 🚨 MARC'S RULE: "Can only include data through Week 4 in a Week 5 game."
--
-- fct_player_leader_week's row for week N must accumulate weeks strictly BEFORE N. The window
-- frame that does it ends at `1 preceding`; changing that one word to `current row` produces a
-- leaderboard containing the box score of the game it is displayed beside — a leakage defect that
-- looks entirely correct on every row, because the numbers are real and merely one game too new.
-- This is the same assertion, and the same reasoning, as
-- assert_record_through_week_excludes_the_current_week.
--
-- ⚠️ ORDERED ON (season_type_ordinal, week), NEVER week ALONE. Postseason week numbers restart at
-- 1, so a bowl game compared on `week <` is treated as preceding an October fixture. This was
-- written with `week <` first and reported two false rows for exactly that reason — the trap is
-- as real in the test as in the model, and it is the reason the ordinal is joined in below rather
-- than assumed.
--
-- ⚠️ ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW. The first version of this test ran a
-- join-plus-aggregate for each of 74,065 leader rows and had not finished in ten minutes. A097
-- rewrote three correlated subqueries into one grouped pass for the same reason and took a
-- distribution model from 28 minutes to 23 seconds. The lookup below is a tiny distinct list
-- rather than a second scan of dim_team_week's 485k rows.
with season_type_order as (

    select distinct season, season_type, season_type_ordinal
    from {{ ref('dim_team_week') }}
    where season >= 2024

),

yardage as (

    select y.season, y.team_id, y.player_id, y.panel, y.week, y.week_yards,
           o.season_type_ordinal
    from {{ ref('fct_player_yardage_week') }} y
    join season_type_order o
      on  o.season      = y.season
      and o.season_type = y.season_type

),

recomputed as (

    select
        l.season, l.season_type, l.week, l.team_id, l.panel, l.player_id, l.player_name,
        l.yards_through_prior_week                as model_says,
        coalesce(sum(ya.week_yards), 0)           as sum_of_strictly_earlier_weeks
    from {{ ref('fct_player_leader_week') }} l
    left join yardage ya
      on  ya.season    = l.season
      and ya.team_id   = l.team_id
      and ya.player_id = l.player_id
      and ya.panel     = l.panel
      and (ya.season_type_ordinal, ya.week) < (l.season_type_ordinal, l.week)
    group by l.season, l.season_type, l.week, l.team_id, l.panel, l.player_id,
             l.player_name, l.yards_through_prior_week

)

select season, season_type, week, team_id, panel, player_id, player_name,
       model_says, sum_of_strictly_earlier_weeks,
       'a week-N leaderboard must not contain week N' as rule
from recomputed
where model_says is distinct from sum_of_strictly_earlier_weeks
