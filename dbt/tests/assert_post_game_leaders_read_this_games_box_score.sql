-- R-723. Every figure on a post-game card must come from THE GAME THE CARD IS ATTACHED TO.
--
-- 🚨 THIS IS THE LEAKAGE RULE'S MIRROR IMAGE, AND IT IS THE DEFECT THAT WOULD BE HARDEST TO SEE.
-- `srv_game_team_leader_through_prior_week` must NOT contain the game it sits beside;
-- `srv_game_team_leader_in_this_game` must contain NOTHING ELSE. The two views differ by one
-- suffix, are built from the same panels with the same macro, and a card fed from the wrong window
-- renders perfectly: real players, plausible yardage, three filled slots, the wrong game.
--
-- ⚠️ A TEST THAT ASSERTS "THREE CARDS APPEARED" CANNOT SEE IT. Nor can a row count, nor a null
-- check, nor the documentation guard. What catches it is recomputing each player's figures from
-- `fct_player_game_stat` FOR THAT GAME ID and comparing — an independent recomputation, not a
-- restatement of the view's own expression.
--
-- ⚠️ AND IT ASSERTS THE SLOT COLUMNS, NOT ONLY `game_yards`. The slots are what a reader sees, and
-- they come from a shared macro that the preview view also calls — so a future edit to
-- `player_card_slots` that reached for the wrong argument would show up here rather than on a page.
with box as (

    {% for panel, category in [('passing', 'receiving'), ('rushing', 'rushing')] %}
    select
        s.game_id, s.team_id, s.player_id, '{{ panel }}' as panel,
        sum(case when s.stat_type = 'YDS' then s.stat_value end) as yards,
        sum(case when s.stat_type = '{{ 'REC' if panel == 'passing' else 'CAR' }}'
                 then s.stat_value end)                          as slot_1,
        sum(case when s.stat_type = 'TD' then s.stat_value end)  as touchdowns
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = '{{ category }}'
      and s.stat_type in ('YDS', '{{ 'REC' if panel == 'passing' else 'CAR' }}', 'TD')
      and s.stat_value is not null
      and s.season >= 2024
    group by s.game_id, s.team_id, s.player_id
    union all
    {% endfor %}

    -- The total panel: passing PLUS rushing yards and touchdowns, for athletes listed at QB.
    select
        s.game_id, s.team_id, s.player_id, 'total' as panel,
        sum(case when s.stat_type = 'YDS'   then s.stat_value end) as yards,
        sum(case when s.stat_type = 'C/ATT' then s.stat_made end)  as slot_1,
        sum(case when s.stat_type = 'TD'    then s.stat_value end) as touchdowns
    from {{ ref('fct_player_game_stat') }} s
    join {{ ref('dim_athlete') }} a
      on a.athlete_sk = s.athlete_sk and a.position = 'QB'
    where s.stat_category in ('passing', 'rushing')
      and s.stat_type in ('YDS', 'TD', 'C/ATT')
      and (s.stat_value is not null or s.stat_type = 'C/ATT')
      and s.season >= 2024
    group by s.game_id, s.team_id, s.player_id

)

select
    v.game_id, v.team_id, v.panel, v.player_name, v.leader_rank,
    v.game_yards      as view_yards,
    b.yards           as box_yards,
    v.stat_1_value    as view_slot_1,
    b.slot_1          as box_slot_1,
    v.stat_3_value    as view_slot_3,
    case
      when b.game_id is null
        then 'a card exists for a player with no box-score line in this game'
      when v.game_yards is distinct from b.yards
        then 'the ranked yards are not this game''s yards'
      when v.stat_2_value is distinct from b.yards
        then 'slot 2 is not this game''s yards'
      when v.stat_1_value is distinct from b.slot_1
        then 'slot 1 is not this game''s figure'
      when v.panel <> 'rushing' and v.stat_3_value is distinct from b.touchdowns
        then 'slot 3 is not this game''s touchdowns'
    end as rule
from {{ ref('srv_game_team_leader_in_this_game') }} v
left join box b
       on  b.game_id   = v.game_id
       and b.team_id   = v.team_id
       and b.player_id = v.player_id
       and b.panel     = v.panel
where b.game_id is null
   or v.game_yards    is distinct from b.yards
   or v.stat_2_value  is distinct from b.yards
   or v.stat_1_value  is distinct from b.slot_1
   or (v.panel <> 'rushing' and v.stat_3_value is distinct from b.touchdowns)
