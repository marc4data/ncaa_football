{{ config(severity='error') }}
-- R-694. 🚨 §4.2 — THE PAGE DOES NOT DIVIDE, SO THE DENOMINATOR TRAVELS WITH THE NUMBER.
--
-- Usage is strongly positional. Measured medians: QB 0.551, RB 0.134, WR 0.058, TE 0.041. A circle
-- filled against a 0-1 scale therefore leaves every receiver about 6% full — visually empty, and
-- indistinguishable from DID NOT PLAY, which is the one thing the circles exist to show. Cowork's
-- ruling is that the fill is relative to THAT PLAYER'S OWN MAXIMUM in the window.
--
-- If `usage_total_max_in_window` is dropped the page has to compute it, which is the rule this
-- asserts. If it is merely WRONG the circles are silently mis-scaled, so the value is checked too:
-- it must equal the largest usage_total among the rows actually shown for that leader, and no mark
-- may exceed it.
with expected as (

    select
        game_id, team_id, panel, player_id,
        max(usage_total) as should_be,
        count(*)         as should_count
    from {{ ref('srv_game_team_leader_usage') }}
    group by game_id, team_id, panel, player_id

),

stated as (

    select distinct
        game_id, team_id, panel, player_id, player_name,
        usage_total_max_in_window,
        usage_games_in_window
    from {{ ref('srv_game_team_leader_usage') }}

)

select
    s.game_id, s.team_id, s.panel, s.player_id, s.player_name,
    s.usage_total_max_in_window as stated_max,
    e.should_be                 as actual_max,
    s.usage_games_in_window     as stated_count,
    e.should_count              as actual_count,
    'the denominator must match the marks it scales' as rule
from stated s
join expected e
  on  e.game_id   = s.game_id
  and e.team_id   = s.team_id
  and e.panel     = s.panel
  and e.player_id = s.player_id
where s.usage_total_max_in_window is distinct from e.should_be
   or s.usage_games_in_window     is distinct from e.should_count
