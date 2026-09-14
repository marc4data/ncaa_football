{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only`: it reads `fct_coach_team_season` against `stg_coach_season`, and
-- no gated DAG rebuilds both — `/coaches` is a HISTORY_FULL endpoint fetched by the backfill, not
-- by the two-hourly scores DAG. `ci/check_test_refresh_scope.py` is the guard that would otherwise
-- stop that DAG's publish (R-672).
--
-- R-766. A TENURE IS A RUN OF CONSECUTIVE SEASONS AT ONE SCHOOL, AND A GAP YEAR ENDS IT.
--
-- 🚨 THE DEFECT THIS EXISTS FOR LEAVES EVERY ROW REAL. Derive the boundary from `hired_at` and
-- every coach still gets a tenure — it is simply the WRONG ONE for anybody hired more than once,
-- because `hired_at` belongs to the COACH and repeats on every season row. Steve Addazio carries
-- 2012-12-04 on all seven of his Boston College seasons; it is null entirely for older coaches.
--
-- ⚠️ AND A CARD READING "in his 4th season" WHEN IT IS HIS 12th IS THE KIND OF ERROR A READER
-- SPOTS AND WE DO NOT. Measured cases this must keep right:
--
--     Barry Alvarez   Wisconsin   1990-2005, 2012, 2014      three tenures
--     Bob Neyland     Tennessee   1926-1934, 1936-1940, 1946-1952
--     Chris Ault      Nevada      1992, 1994-1995, 2004-2012
--
-- ⚠️ R-760, ASKED OF THIS TEST: what would have to be wrong for it to fire? The boundary read from
-- a date instead of the season sequence, or the partition losing `team_id` so a coach's two
-- schools merged into one run. Both are single-line edits, and both change the answer without
-- changing the row count.
--
-- THREE CLAIMS, recomputed from staging INDEPENDENTLY rather than re-derived from the model:
--   1. every season inside a tenure's span is a season the coach actually worked there;
--   2. the season immediately before a tenure's first season is NOT one he worked there —
--      otherwise the tenure started too late and two runs were split that should be one;
--   3. the season immediately after a tenure's last is likewise absent.
with worked as (

    select distinct coach_id, team_id, season from {{ ref('stg_coach_season') }}

),

spans as (

    select distinct coach_id, team_id, tenure_number, tenure_first_season, tenure_last_season,
                    tenure_seasons
    from {{ ref('fct_coach_team_season') }}

)

select
    s.coach_id, s.team_id, s.tenure_number,
    s.tenure_first_season, s.tenure_last_season, s.tenure_seasons,
    case
      when s.tenure_last_season - s.tenure_first_season + 1 <> s.tenure_seasons
        then 'a tenure span with a hole in it — the seasons are not consecutive'
      when exists (select 1 from worked w
                   where w.coach_id = s.coach_id and w.team_id = s.team_id
                     and w.season = s.tenure_first_season - 1)
        then 'the season before this tenure was also worked — two runs split that are one'
      when exists (select 1 from worked w
                   where w.coach_id = s.coach_id and w.team_id = s.team_id
                     and w.season = s.tenure_last_season + 1)
        then 'the season after this tenure was also worked — the run was cut short'
    end as rule
from spans s
where s.tenure_last_season - s.tenure_first_season + 1 <> s.tenure_seasons
   or exists (select 1 from worked w
              where w.coach_id = s.coach_id and w.team_id = s.team_id
                and w.season = s.tenure_first_season - 1)
   or exists (select 1 from worked w
              where w.coach_id = s.coach_id and w.team_id = s.team_id
                and w.season = s.tenure_last_season + 1)
