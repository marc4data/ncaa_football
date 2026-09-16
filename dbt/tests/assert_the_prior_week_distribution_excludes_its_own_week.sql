{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for its family's reason (R-672): it compares marts the two-hourly
-- scores DAG does not rebuild on one cadence, and `ci/check_test_refresh_scope.py` would otherwise
-- stop that DAG's publish.
--
-- THE LEAKAGE BOUNDARY, ASSERTED RATHER THAN INTENDED. A143, cfdb-main-R-973.
--
-- Marc's rule, which this whole family exists to keep: *"can only include data through Week 4 in a
-- Week 5 game… That's leakage and unacceptable."* R-463.
--
-- 🚨 THIS TEST IS THE COMPENSATING CONTROL FOR A DEPARTURE THE MODEL WAS FORCED INTO, AND THAT IS
-- WHY IT IS NOT OPTIONAL. `fct_player_leader_week` enforces the same rule in a WINDOW FRAME and
-- argues, correctly, that this is stronger than a predicate: *"a leakage rule enforced by a filter
-- is a rule one careless join removes… Delete any line you like and the leakage rule survives,
-- because it lives in the frame."* ⚠️ THAT SHAPE IS UNAVAILABLE TO A PERCENTILE — Postgres refuses
-- it in as many words:
--
--     OVER is not supported for ordered-set aggregate percentile_cont
--
-- So the boundary in `fct_game_team_metric_distribution_through_prior_week` IS a join predicate,
-- it IS the thing that header warns about, and an assertion is the only way to get the guarantee
-- back. **A single character — `<` becoming `<=` — is the whole defect, and it changes no row
-- count, produces no null, and leaves every published figure a real percentile of a real
-- population.** Nothing but this test can see it.
--
-- ⚠️ RECOMPUTED FROM THE SOURCE, NOT READ BACK FROM THE MODEL. A test that re-derives a column
-- from that column proves nothing (R-768: "it was testing a list the test wrote"). This walks
-- `int_game_team_metric_value` — the model's input — and asks independently what the window should
-- have contained.
--
-- ⚠️ ORDERED BY (season_type_ordinal, week), because the model is: a postseason week 1 inherits the
-- whole regular season, and a test that compared on `week` alone would call that correct row a
-- failure. `fct_team_yardage_week`'s rule — "postseason week numbers restart at 1, so ordering on
-- week would sort a bowl game into the middle of October."
--
-- 🚨 R-760, ASKED OF THIS TEST, AND BRANCH 2 IS THE ANSWER. Branch 1 can only fire on a week that
-- HAS games of its own — everywhere else `< W` and `<= W` are the same set and the assertion is
-- vacuously true. 📊 That is most rows: for 2026 only week 2 is discriminating, because weeks 3-15
-- are unplayed. **So branch 2 asserts that discriminating weeks still EXIST.** If the data ever
-- stops containing one, this test has quietly stopped testing anything and says so instead.
with ordinals as (

    select distinct season, season_type, season_type_ordinal, week
    from {{ ref('dim_team_week') }}

),

source as (

    select v.season, v.season_type, v.week, v.metric, v.value, o.season_type_ordinal
    from {{ ref('int_game_team_metric_value') }} v
    join ordinals o
      on o.season = v.season and o.season_type = v.season_type and o.week = v.week
    where v.value is not null

),

-- What the window SHOULD hold, and what it would hold if the boundary slipped by one character.
recomputed as (

    select
        s.season, s.season_type, s.week, x.metric,
        count(*) filter (where (x.season_type_ordinal, x.week) <  (s.season_type_ordinal, s.week))
            as strictly_before,
        count(*) filter (where (x.season_type_ordinal, x.week) <= (s.season_type_ordinal, s.week))
            as through_this_week
    from ordinals s
    join source x
      on x.season = s.season
     and (x.season_type_ordinal, x.week) <= (s.season_type_ordinal, s.week)
    group by s.season, s.season_type, s.week, x.metric

),

failures as (

    -- 1. THE PUBLISHED COUNT IS THE STRICTLY-BEFORE COUNT. Under `<=` every discriminating week
    --    publishes `through_this_week` instead, and this fires on all of them.
    select
        p.season, p.season_type, p.week, p.metric,
        p.n                  as published_n,
        r.strictly_before    as should_be,
        r.through_this_week  as would_be_under_leakage,
        'the window must end STRICTLY BEFORE this week — R-463, Marc''s leakage rule' as rule
    from {{ ref('fct_game_team_metric_distribution_through_prior_week') }} p
    join recomputed r
      on  r.season = p.season and r.season_type = p.season_type
     and r.week = p.week and r.metric = p.metric
    where p.n is distinct from r.strictly_before

    union all

    -- 2. 🚨 AND THE TEST ITSELF IS STILL CAPABLE OF FAILING. A week where the two windows agree
    --    cannot catch a slipped boundary, so if NO week discriminates, branch 1 is decoration.
    select
        null::int, null::{{ dbt.type_string() }}, null::int, null::{{ dbt.type_string() }},
        null::bigint, null::bigint, null::bigint,
        'no week in the data has games of its own, so branch 1 cannot fail — this test has '
        'stopped testing the boundary rather than passing it' as rule
    from (
        select count(*) as discriminating
        from recomputed
        where through_this_week > strictly_before
    ) guard
    where guard.discriminating = 0

)

select * from failures
