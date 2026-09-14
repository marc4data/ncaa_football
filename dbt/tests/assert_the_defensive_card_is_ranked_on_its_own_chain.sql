{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only`: it reads `srv_game_team_leader_in_this_game` against
-- `fct_player_game_stat`, and no gated DAG rebuilds both. `ci/check_test_refresh_scope.py` is the
-- guard that would otherwise stop that DAG's publish (R-672).
--
-- R-839/R-841. THE DEFENSIVE PANEL MUST BE RANKED ON TACKLES, THEN SOLO TACKLES, THEN TFL.
--
-- 🚨 THE DEFECT THIS EXISTS FOR EMPTIES THE PANEL WITHOUT ERRORING. The other three panels rank
-- on `game_yards`, and ranking the defensive one the same way is the single most natural edit
-- anybody will make here — the column is right there in the same select. A DEFENDER HAS NO
-- YARDS, so the expression is NULL for every defensive row and the panel comes back EMPTY.
--
-- ⚠️ AND AN EMPTY PANEL PASSES MOST ASSERTIONS ANYONE WOULD WRITE — §6 mode 2, an expression
-- true by construction (R-760). "the view has rows" passes on the other three panels. "no row has
-- a null rank" passes vacuously. "count >= 0" passes always. ✅ SO THIS PINS A NAMED PLAYER IN A
-- NAMED GAME AT A NAMED RANK, and separately recomputes the whole ordering from the fact table.
--
-- 🚨 THE ANCHOR IS CHOSEN SO THAT THE TIEBREAK ITSELF IS LOAD-BEARING, which is the part a
-- weaker anchor would miss. Alabama, game 401628319, 2024:
--
--     rank 1   Jihaad Campbell   TOT 9   SOLO 6   TFL 1
--     rank 2   Deontae Lawson    TOT 9   SOLO 3   TFL 1
--     rank 3   Brayson Hubbard   TOT 6   SOLO 5   TFL 1
--
-- ⚠️ CAMPBELL AND LAWSON HAVE THE SAME TACKLE COUNT. Ranked on tackles alone they are JOINTLY
-- FIRST and there is no rank 2 — so this anchor fails not only the yards break but also the
-- lazier "just rank on TOT" version that 43.2% of team-games cannot distinguish. The solo count
-- is what separates them and the assertion is exactly that.
--
-- ⚠️ THE ANCHOR IS SCOPED TO ITS GAME, AND THAT CONDITION IS DELIBERATE — A127 SHIPPED THE
-- UNCONDITIONAL FORM AND CI CAUGHT IT. `ci/fixtures.sql` is a small synthetic raw-layer load and
-- does not carry game 401628319. So the claim is conditional on the GAME being in the view; if it
-- is absent, as in any fixture, the branch says nothing. 🚨 IN CI THIS BRANCH IS VACUOUS AND ONLY
-- THE RECOMPUTATION BELOW IS WORKING — naming that is the difference between a scoped assertion
-- and a silently dead one.
--
-- ONE GROUPED PASS, NOT A CORRELATED SUBQUERY PER ROW — A097, A106 and A120 all paid for that.
-- 🚨 SCOPED ON THE GAME EXISTING AT ALL, NOT ON THE DEFENSIVE PANEL HAVING ROWS — and the
-- difference is the whole point. An earlier draft of this test keyed the guard on
-- `panel = 'defensive'` rows being present, which meant AN EMPTY DEFENSIVE PANEL SWITCHED THE
-- ASSERTION OFF: the yards break empties the panel, the guard finds nothing, and the test passes.
-- That is §6 mode 2 committed inside the very test written to catch it.
-- ✅ So the condition is "is this GAME in the view", which is true whenever the offensive panels
-- built, and false only in a fixture that does not carry the game.
with anchor_game as (

    select
        count(*) filter (where panel = 'defensive')                   as rows_in_group,
        count(*)                                                      as rows_in_game,
        -- string_agg, not max: a tie SHARES a rank on this view, so a rank may hold more than
        -- one man and the anchor must assert the whole set rather than an arbitrary member.
        string_agg(player_id, ',' order by player_id)
            filter (where panel = 'defensive' and leader_rank = 1) as rank_1,
        string_agg(player_id, ',' order by player_id)
            filter (where panel = 'defensive' and leader_rank = 2) as rank_2,
        string_agg(player_id, ',' order by player_id)
            filter (where panel = 'defensive' and leader_rank = 3) as rank_3,
        max(leader_rank) filter (where panel = 'defensive')            as deepest_rank
    from {{ ref('srv_game_team_leader_in_this_game') }}
    where game_id = 401628319 and team_id = 333

),

-- THE ORDERING REBUILT FROM THE FACT TABLE, independently of the view. Not a property of the
-- output: the view must agree with a ranking this test derives itself.
source as (

    select
        s.game_id, s.team_id, s.player_id,
        max(s.stat_value) filter (where s.stat_type = 'TOT')  as tot,
        max(s.stat_value) filter (where s.stat_type = 'SOLO') as solo,
        max(s.stat_value) filter (where s.stat_type = 'TFL')  as tfl
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'defensive'
      and s.stat_type in ('TOT', 'SOLO', 'TFL')
      and s.stat_value is not null
      and s.season >= 2024
    group by s.game_id, s.team_id, s.player_id
    having max(s.stat_value) filter (where s.stat_type = 'TOT') > 0

),

source_ranked as (

    select game_id, team_id, player_id, tot, solo, tfl,
           rank() over (partition by game_id, team_id
                        order by tot desc, solo desc, tfl desc) as expected_rank
    from source

),

published as (

    select game_id, team_id, player_id, leader_rank, game_tackles, game_solo_tackles,
           game_tackles_for_loss, game_yards
    from {{ ref('srv_game_team_leader_in_this_game') }}
    where panel = 'defensive'

)

select
    p.game_id, p.team_id, p.player_id,
    p.leader_rank        as published_rank,
    sr.expected_rank,
    case
      when sr.expected_rank is null
        then 'a published defensive leader is not a top-three defender in the source'
      when p.game_yards is not null
        then 'a defensive row carries yards — a tackler has none, so this panel is being fed offence'
      when p.game_tackles is null
        then 'a defensive row carries no tackle count, so nothing ranked it'
      else 'the published defensive rank is not tackles-then-solo-then-TFL'
    end as rule
from published p
left join source_ranked sr
       on  sr.game_id   = p.game_id
       and sr.team_id   = p.team_id
       and sr.player_id = p.player_id
       and sr.expected_rank <= 3
where sr.expected_rank is null
   or p.leader_rank is distinct from sr.expected_rank
   or p.game_yards is not null
   or p.game_tackles is null

union all

select
    401628319, 333, 'anchor',
    deepest_rank, 3,
    case
      when rows_in_group = 0
        then 'the anchor game has no defensive panel at all — the panel is empty, '
             || 'which is exactly what ranking defenders on yards produces'
      when rank_1 is distinct from '4685287'
        then 'rank 1 is not Jihaad Campbell — 9 tackles with 6 solo leads this group'
      when rank_2 is distinct from '4432725'
        then 'rank 2 is not Deontae Lawson — he ties Campbell on tackles and loses on solos, '
             || 'so a ranking without the solo tiebreak produces two rank 1s and no rank 2'
      else 'rank 3 is not Brayson Hubbard'
    end
from anchor_game
where rows_in_game > 0
  and (rows_in_group = 0
    or rank_1 is distinct from '4685287'
    or rank_2 is distinct from '4432725'
    or rank_3 is distinct from '5077638')
