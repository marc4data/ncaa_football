{{ config(severity='error') }}
-- One row per player x game x category x stat type, on the view the leaderboards read (R-430).
--
-- WHY THIS IS ON THE SERVING VIEW AND NOT ONLY THE MART. A060 (R-392) found 502 duplicate
-- rows in fct_player_game_stat, caused by CFBD listing the same athlete twice inside one
-- game's payload, and deduplicated at the mart. A061 then found the same duplication in
-- staging and fixed it there too. Both are upstream of this view — but the Looking Back
-- defensive board reads THIS view, and a board that sums tackles over a duplicated key is
-- wrong in the direction that looks impressive. The assertion belongs where the page reads.
--
-- tests/test_today_page.py holds the same rule as a unit test and is proven red against a
-- simulated duplicate, because this one can only fail once real data breaks.
select game_id, player_id, stat_category, stat_type, count(*) as rows_found
from {{ ref('srv_player_game_log') }}
group by 1, 2, 3, 4
having count(*) > 1
