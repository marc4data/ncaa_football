{{ config(severity='error') }}
-- srv_game is one row per game, and a join must not change that (R-394).
--
-- THE DEFECT THIS SHAPE OF CHANGE PRODUCES. Adding the win-probability summary columns is a
-- join from a mart that is game-grain today. If it ever stops being game-grain -- a second
-- provider, a re-run that appends rather than replaces, a key that gains a column -- srv_game
-- silently fans out. Every count on every page that reads it is then wrong, in the direction
-- that looks like more football having been played.
--
-- Cheap, and it is the assertion the prompt asked for by name rather than a proxy for it.
select game_id, count(*) as rows_found
from {{ ref('srv_game') }}
group by game_id
having count(*) > 1
