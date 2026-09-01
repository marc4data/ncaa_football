-- No single game may sit on /plays/stats' 2,000-record ceiling.
--
-- CFBD's spec states the endpoint is "limited to 2,000 records" per request. cfdb used to
-- fetch it per season-week, and a week has far more than 2,000 stat lines, so every request
-- returned exactly 2,000 and stopped — with a 200 status and nothing to say anything was
-- dropped. Coverage was 375 of 3,410 games, and the survivors were whatever the API returned
-- first: 118 of the 177 covered 2024 games were SEC.
--
-- THE UNIT OF TRUNCATION MOVED WHEN THE FETCH DID, AND SO DID THIS TEST.
--
-- Its first version asserted on rows per season-WEEK, which was right while a week was one
-- request. Now that the endpoint fans out per game, a week legitimately holds far more than
-- 2,000 rows — 26,704 in 2024 week 1 — and the old assertion would have fired on healthy
-- data. Testing the aggregate stopped being the same question as testing the request.
--
-- A GAME is now one request, so a game is the unit that can be capped. Measured after the
-- backfill: 1,884 games covered, 199.5 stat lines on average, 356 at the maximum, and none
-- within an order of magnitude of the ceiling. That headroom is what makes error severity
-- honest here — the previous version warned because every week failed it and no change in
-- this repo could fix that. This one passes, and a failure would mean a single game produced
-- 2,000 stat lines, which is either a genuine outlier worth seeing or the fan-out having
-- silently reverted to a coarser scope.
select game_id, season, week, count(*) as rows_returned
from {{ ref('fct_play_stat') }}
group by game_id, season, week
having count(*) >= 2000
