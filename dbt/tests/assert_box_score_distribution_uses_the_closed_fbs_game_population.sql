{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for the reason its siblings carry: it reads marts that the
-- two-hourly scores DAG does not rebuild on the same cadence as this distribution, and
-- `ci/check_test_refresh_scope.py` is the guard that would otherwise stop that DAG's publish
-- (R-672).
--
-- R-808, REWRITTEN BY A142 (cfdb-main-R-962). The distribution must describe THE SAME POPULATION
-- as the numbers drawn on top of it — that claim is unchanged and is still what this file is for.
-- ⚠️ WHAT CHANGED IS THE POPULATION, so the assertion moved with it rather than being deleted.
--
--     was   every team-game of an FBS TEAM              `dim_team.classification = 'fbs'`, per row
--     now   every team-game of a COMPLETED GAME         the classification asked of the FIXTURE
--           INVOLVING AN FBS SCHOOL, both sides
--
-- 🚨 THE OLD RULE'S DEFECT LEFT EVERY NUMBER REAL, WHICH IS WHY IT SURVIVED. An FBS team's yards
-- against an FCS opponent entered the pool; the opponent's matching figure never did. Measured on
-- 2026 regular `total_yards`, the same games produced a median of 398.0 read as GAINED and 322.0
-- read as ALLOWED — a 76-yard gap between two descriptions of one set of fixtures. 85 of 285 FBS
-- team-games this season had no mirror. `int_game_team_metric_value` carries the full measurement.
--
-- ⚠️ THE CONCERN THE OLD HEADER RAISED IS NOT DISMISSED, AND IT IS RESTATED HERE SO NOBODY HAS TO
-- GO TO THE GIT LOG FOR IT: *"a reader comparing an FBS team's 180 rushing yards against a
-- distribution that includes Division II opponents is told they had an ordinary game when they had
-- a good one."* ✅ That is a real cost and it is paid knowingly — the old pool was never the clean
-- FBS-only set it read as, because it already contained every FBS blowout OF a non-FBS side and
-- only that flattering half. Marc ruled on the trade: *"probably need to include both sides of a
-- game involving an FBS school."*
--
-- ⚠️ THE POPULATION RULE LIVES IN ONE PLACE — the intermediate — and this test recomputes it
-- INDEPENDENTLY from the marts rather than reading the intermediate back. A test that re-derives a
-- column from that column proves nothing; this one fails if the rule is dropped, narrowed, widened,
-- or spelled differently in a later edit.
--
-- ⚠️ R-760, ASKED OF THIS TEST: what would have to be wrong for it to fire? Restoring the per-team
-- `classification = 'fbs'` filter; making either downstream join inner again; pointing the
-- intermediate at a different source; losing `is_completed`. All four are single-line edits
-- somebody could plausibly make, and all four change the answer without changing the shape.
--
-- 🚨 AND BRANCH 2 IS THE ONE THAT MATTERS MOST, because it asserts the PROPERTY rather than the
-- numbers. Mirror closure is what makes gained and allowed the same multiset; the percentiles in
-- branch 1 are a consequence of it. A future edit could keep branch 1 green over a pool that had
-- lost a handful of mirrors — the percentiles would move together — and branch 2 could not.
-- 📊 Measured over every season at the time of writing: 166,298 pool rows, 0 without a mirror.
--
-- ⚠️ ONE GROUPED PASS PER SIDE, joined — not a correlated subquery per row (A097, A106, A120).
-- And one metric rather than all eighteen: the population rule is shared, so proving it on a dense
-- metric proves it for the set, and eighteen recomputations of a 2.7M-row table is a cost with no
-- extra coverage. `assert_gained_and_allowed_match_at_game_grain` uses a DIFFERENT metric, so the
-- pair covers two.
with fbs_games as (

    select t.game_id
    from {{ ref('fct_game_team') }} t
    left join {{ ref('dim_team') }} d
      on d.season = t.season and d.team_id = t.team_id
    where t.is_completed
    group by t.game_id
    having bool_or(d.classification = 'fbs')

),

pool as (

    select t.season, t.season_type, t.week, t.game_id, t.team_id, t.opponent_team_id,
           t.rushing_yards
    from {{ ref('fct_game_team') }} t
    join fbs_games g
      on g.game_id = t.game_id
    where t.is_completed

),

independent as (

    select
        p.season, p.season_type, p.week,
        percentile_cont(0.25) within group (order by p.rushing_yards) as p25,
        percentile_cont(0.50) within group (order by p.rushing_yards) as p50,
        percentile_cont(0.75) within group (order by p.rushing_yards) as p75,
        count(p.rushing_yards)                                        as n
    from pool p
    group by p.season, p.season_type, p.week
    having count(p.rushing_yards) > 1

),

failures as (

    -- 1. THE PUBLISHED DISTRIBUTION IS THE ONE THIS POPULATION PRODUCES.
    select
        p.season, p.season_type, p.week,
        'the distribution must describe the closed FBS-game population the page draws on' as rule
    from {{ ref('fct_game_team_metric_distribution') }} p
    join independent i
      on  i.season = p.season and i.season_type = p.season_type and i.week = p.week
    where p.metric = 'rushing_yards'
      and (p.n   is distinct from i.n
        or p.p25 is distinct from i.p25
        or p.p50 is distinct from i.p50
        or p.p75 is distinct from i.p75)

    union all

    -- 2. 🚨 THE POOL IS CLOSED UNDER `mirror`. Every team-game in it has the other side of its own
    --    fixture in it too — which is the property, not a symptom of it.
    select
        p.season, p.season_type, p.week,
        'a team-game is in the distribution pool without the other side of its own game' as rule
    from pool p
    left join pool m
      on m.game_id = p.game_id and m.team_id = p.opponent_team_id
    where m.team_id is null

)

select * from failures
