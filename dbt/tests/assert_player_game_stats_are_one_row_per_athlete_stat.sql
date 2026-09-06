{{ config(severity='error') }}
-- One row per game x team x category x stat type x athlete (R-392).
--
-- THIS IS THE TEST THAT WAS MISSING. The model already builds player_game_stat_sk from
-- exactly these five columns, so 502 rows carried a duplicated surrogate key and nothing
-- said so -- the fact "has a surrogate key" was mistaken for the fact "has a unique one".
--
-- The duplication is upstream, in the CFBD payload, and it will keep arriving; the mart
-- deduplicates it. This fails if that dedupe is removed, or if the source starts repeating
-- an athlete with DIFFERENT values, which would be a different and worse problem -- a real
-- disagreement rather than a copy, and one this model must not silently pick a winner from.
select game_id, team, stat_category, stat_type, player_id, count(*) as rows_found
from {{ ref('fct_player_game_stat') }}
group by 1, 2, 3, 4, 5
having count(*) > 1
