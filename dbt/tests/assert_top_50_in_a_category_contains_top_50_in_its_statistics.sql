-- A177 (cfdb-main-R-1769). Every row that is top 50 in a STATISTIC must also be flagged top 50
-- in its CATEGORY. The category flag is the wider set by construction, and a row inside the
-- narrow one but outside the wide one is impossible unless the partition is wrong.
--
-- 🚨 THIS IS THE CONTAINMENT THE WORKBOOK'S 100% FILL RESTS ON. A175's pivot is full only
-- because fetching on this flag returns every statistic for every player the category admits;
-- if the flag's partition ever lost `player_id` — or gained `stat_type`, which would make it a
-- second spelling of `rank_desc <= 50` — the pivot would silently go back to 28.8% holes and
-- every test asserting "the sheet has rows" would still pass.
--
-- ⚠️ WHAT THIS DELIBERATELY DOES NOT ASSERT is that the wide set is STRICTLY wider. That is
-- true of the real data (3,539 rows against 12,292 in 2025) and is not guaranteed for a small
-- fixture, where a category may hold exactly one statistic and the two sets coincide. A test
-- that fires on a legitimate fixture is a test that gets deleted (2.3.3).
select
    season,
    stat_category,
    stat_type,
    player_id,
    rank_desc,
    is_top_50_in_category
from {{ ref('srv_player_stats') }}
where rank_desc <= 50
  and is_top_50_in_category is not true
