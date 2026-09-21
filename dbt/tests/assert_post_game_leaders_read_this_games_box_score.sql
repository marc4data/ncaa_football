{{ config(tags=['full_refresh_only']) }}
-- 🚨 TAGGED BY A185 (cfdb-main-R-1913), AND THE STRADDLE IS THIS ROUND'S OWN DOING.
-- Putting `srv_player_play` on the game-day selector pulled `dim_athlete` in with it, so
-- this test began reading a FRESH `dim_athlete` against a `fct_player_game_stat` that the
-- scores DAG does not rebuild. `publish_to_serving` sits downstream of `dbt_test`, so it
-- would have STOPPED THE SITE UPDATING on a game day rather than merely gone red.
-- ⚠️ Nothing about this was visible in the diff that caused it — the round added a
-- serving model and inherited a mart's test three edges away.
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
--
-- 🚨 A128 ADDED THE DEFENSIVE PANEL AND THIS TEST CAUGHT IT IMMEDIATELY — 13,078 rows, every one
-- reading "a card exists for a player with no box-score line in this game", because the `box` CTE
-- knew only the three offensive panels. ✅ THE TEST WAS RIGHT AND THE FIX IS TO TEACH IT THE NEW
-- PANEL, never to exempt the panel from it.
--
-- ⚠️ AND SLOT 2 IS NO LONGER "YARDS" FOR EVERY PANEL. It is THE FIGURE THE PANEL RANKS ON —
-- ⚠️ SIX PANELS NOW. A134 added `punting` and `kicking`, and the kicking branch is the first to
-- read `stat_made`/`stat_attempted` instead of `stat_value` — see it for why.
-- yards on the three offensive panels, TACKLES on the defensive one. `game_yards` is still
-- compared against yards separately, and on a defensive row both sides are NULL, which is the
-- assertion that a tackler is never handed offence.
with box as (

    {% for panel, category in [('passing', 'receiving'), ('rushing', 'rushing')] %}
    select
        s.game_id, s.team_id, s.player_id, '{{ panel }}' as panel,
        sum(case when s.stat_type = 'YDS' then s.stat_value end) as yards,
        sum(case when s.stat_type = 'YDS' then s.stat_value end) as slot_2,
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
        sum(case when s.stat_type = 'YDS'   then s.stat_value end) as slot_2,
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

    union all

    -- THE DEFENSIVE PANEL. `yards` is deliberately NULL — a tackler records none, and the
    -- comparison below asserts the view agrees. Slot 1 is the SOLO half of Solo-Ast, slot 2 is
    -- total tackles (the ranking measure), slot 3 is TFL.
    select
        s.game_id, s.team_id, s.player_id, 'defensive' as panel,
        null::numeric                                          as yards,
        max(s.stat_value) filter (where s.stat_type = 'TOT')   as slot_2,
        max(s.stat_value) filter (where s.stat_type = 'SOLO')  as slot_1,
        max(s.stat_value) filter (where s.stat_type = 'TFL')   as touchdowns
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'defensive'
      and s.stat_type in ('TOT', 'SOLO', 'TFL')
      and s.stat_value is not null
      and s.season >= 2024
    group by s.game_id, s.team_id, s.player_id

    union all

    -- 🚨 THE PUNTING PANEL — A134. `yards` is NULL (a punter records no rushing or receiving
    -- yards), slot 1 is PUNT yards, slot 2 is punts (the ranking measure) and slot 3 is the
    -- average. ⚠️ THE TEST WAS RIGHT AND THE FIX IS TO TEACH IT THE NEW PANEL, never to exempt
    -- the panel from it — A128's words, and this is the second time they have been needed.
    select
        s.game_id, s.team_id, s.player_id, 'punting' as panel,
        null::numeric                                          as yards,
        max(s.stat_value) filter (where s.stat_type = 'NO')    as slot_2,
        max(s.stat_value) filter (where s.stat_type = 'YDS')   as slot_1,
        max(s.stat_value) filter (where s.stat_type = 'AVG')   as touchdowns
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'punting'
      and s.stat_type in ('NO', 'YDS', 'AVG')
      and s.stat_value is not null
      and s.season >= 2024
    group by s.game_id, s.team_id, s.player_id

    union all

    -- 🚨 THE KICKING PANEL — A134, AND IT IS THE ONE THAT READS `stat_made`/`stat_attempted`
    -- RATHER THAN `stat_value`. FG and XP are made/attempted pairs whose `stat_value` is null on
    -- all 7,842 rows of each; a branch written like the five above would compare null to null and
    -- pass while asserting nothing. Slot 1 is FG made, slot 2 is FG+XP attempts (the ranking
    -- measure), slot 3 is points.
    select
        s.game_id, s.team_id, s.player_id, 'kicking' as panel,
        null::numeric                                                    as yards,
        sum(s.stat_attempted) filter (where s.stat_type in ('FG', 'XP')) as slot_2,
        sum(s.stat_made)      filter (where s.stat_type = 'FG')          as slot_1,
        max(s.stat_value)     filter (where s.stat_type = 'PTS')         as touchdowns
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'kicking'
      and s.stat_type in ('FG', 'XP', 'PTS')
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
      when v.stat_2_value is distinct from b.slot_2
        then 'slot 2 is not this game''s ranking figure — yards, or tackles on the defensive panel'
      when v.stat_1_value is distinct from b.slot_1
        then 'slot 1 is not this game''s figure'
      when v.panel <> 'rushing' and v.stat_3_value is distinct from b.touchdowns
        then 'slot 3 is not this game''s figure — touchdowns, TFL on the defensive panel, '
             'the punting average, or kicking points'
    end as rule
from {{ ref('srv_game_team_leader_in_this_game') }} v
left join box b
       on  b.game_id   = v.game_id
       and b.team_id   = v.team_id
       and b.player_id = v.player_id
       and b.panel     = v.panel
where b.game_id is null
   or v.game_yards    is distinct from b.yards
   or v.stat_2_value  is distinct from b.slot_2
   or v.stat_1_value  is distinct from b.slot_1
   or (v.panel <> 'rushing' and v.stat_3_value is distinct from b.touchdowns)
