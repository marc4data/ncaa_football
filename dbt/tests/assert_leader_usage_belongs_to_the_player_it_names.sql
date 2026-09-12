{{ config(severity='error') }}
-- R-694. 🚨 THE BREAK THIS EXISTS FOR IS INVISIBLE ON THE PAGE AND A READER WOULD BELIEVE IT.
--
-- Attaching one game's usage to a different game — or one player's to another — changes a circle
-- from 20% full to 90% full and nothing on screen says anything is wrong. There is no shape, no
-- gap and no error state; it simply reads as a player who was heavily involved.
--
-- So every row of the serving object is checked back against the fact it claims to be showing:
-- the named (usage_game_id, team_id, player_id) must exist in fct_player_usage_game AND carry the
-- same usage_total. A mis-attached row either finds no match or finds a different number.
select
    u.game_id,
    u.team_id,
    u.player_id,
    u.player_name,
    u.usage_game_id,
    u.usage_total     as serving_says,
    f.usage_total     as fact_says,
    'usage must be this player''s, from the game it names' as rule
from {{ ref('srv_game_team_leader_usage') }} u
left join {{ ref('fct_player_usage_game') }} f
  on  f.game_id   = u.usage_game_id
  and f.team_id   = u.team_id
  and f.player_id = u.player_id
where f.game_id is null
   or f.usage_total is distinct from u.usage_total
