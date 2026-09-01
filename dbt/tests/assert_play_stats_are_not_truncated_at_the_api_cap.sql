-- No season-week may sit exactly on /plays/stats' 2,000-record ceiling.
--
-- CFBD's spec states the endpoint is "limited to 2,000 records" per request, and cfdb
-- fetches it per season-week. A week with more than 2,000 stat lines — which is most weeks —
-- therefore returns exactly 2,000 and stops, with a 200 status and no indication that
-- anything was dropped.
--
-- That is why this test asserts on the SHAPE rather than on a row count being "low". A count
-- landing exactly on a documented cap is not a coincidence, and it is the only signal the
-- API gives. Measured when written: 2024 weeks 2-8 each returned exactly 2,000 rows covering
-- 11 games out of roughly 60 played, and 118 of the 177 covered 2024 games were SEC — the
-- API's ordering showing through, not a fact about football.
--
-- SEVERITY IS WARN, DELIBERATELY, AND THIS IS A DEBT MARKER RATHER THAN A PASSING TEST.
-- Every week currently fails it. Warn keeps the truncation countable and visible on every
-- run instead of failing the build for a condition no code change here can fix; the fix is a
-- per-game fan-out, since the endpoint accepts gameId and a single game averages ~185 stat
-- lines. Raise this to error once that backfill has run.
{{ config(severity='warn') }}

select season, week, count(*) as rows_returned
from {{ ref('fct_play_stat') }}
group by season, week
having count(*) >= 2000
