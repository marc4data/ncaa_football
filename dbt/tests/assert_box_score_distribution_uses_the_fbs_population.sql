{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for the reason its siblings carry: it reads marts that the
-- two-hourly scores DAG does not rebuild on the same cadence as this distribution, and
-- `ci/check_test_refresh_scope.py` is the guard that would otherwise stop that DAG's publish
-- (R-672).
--
-- R-808. The distribution must describe THE SAME POPULATION as the numbers drawn on top of it.
--
-- 🚨 THE DEFECT THIS EXISTS FOR LEAVES EVERY NUMBER REAL. Drop the FBS filter from
-- `int_game_team_metric_value` and the box still draws, the percentiles are still percentiles,
-- the whiskers are still Tukey's — of a different population. A reader comparing an FBS team's
-- 180 rushing yards against a distribution that includes Division II opponents is told they had
-- an ordinary game when they had a good one, and nothing on the page says so.
--
-- ⚠️ THE POPULATION RULE LIVES IN ONE PLACE — `dim_team.classification = 'fbs'`, in the
-- intermediate — and this test recomputes it INDEPENDENTLY from the marts rather than reading
-- the intermediate back. A test that re-derives a column from that column proves nothing; this
-- one would fail if the rule were dropped, widened, or spelled differently in a later edit.
--
-- ⚠️ R-760, ASKED OF THIS TEST: what would have to be wrong for it to fire? Removing or changing
-- the `classification = 'fbs'` join, or pointing the intermediate at a different source. All
-- three are single-line edits somebody could plausibly make, and all three change the answer
-- without changing the shape.
--
-- ⚠️ ONE GROUPED PASS PER SIDE, joined — not a correlated subquery per row (A097, A106, A120).
-- And one metric rather than all eighteen: the population rule is shared, so proving it on a
-- dense metric proves it for the set, and eighteen recomputations of a 2.7M-row table is a cost
-- with no extra coverage.
with independent as (

    select
        t.season, t.season_type, t.week,
        percentile_cont(0.25) within group (order by t.rushing_yards) as p25,
        percentile_cont(0.50) within group (order by t.rushing_yards) as p50,
        percentile_cont(0.75) within group (order by t.rushing_yards) as p75,
        count(t.rushing_yards)                                        as n
    from {{ ref('fct_game_team') }} t
    join {{ ref('dim_team') }} d
      on d.season = t.season and d.team_id = t.team_id
    where d.classification = 'fbs'
    group by t.season, t.season_type, t.week
    having count(t.rushing_yards) > 1

)

select
    p.season, p.season_type, p.week, p.metric,
    p.n         as published_n,
    i.n         as recomputed_n,
    p.p25       as published_p25,
    i.p25       as recomputed_p25,
    p.p50       as published_p50,
    i.p50       as recomputed_p50,
    'the distribution must describe the FBS population the page''s own numbers come from' as rule
from {{ ref('fct_game_team_metric_distribution') }} p
join independent i
  on  i.season = p.season and i.season_type = p.season_type and i.week = p.week
where p.metric = 'rushing_yards'
  and (p.n   is distinct from i.n
    or p.p25 is distinct from i.p25
    or p.p50 is distinct from i.p50
    or p.p75 is distinct from i.p75)
