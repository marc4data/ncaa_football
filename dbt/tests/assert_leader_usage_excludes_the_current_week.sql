{{ config(severity='error') }}
-- R-694. 🚨 MARC'S RULE: "Can only include data through Week 4 in a Week 5 game."
--
-- The usage marks beside a leader are the games he had already played. A mark for the leader's OWN
-- week is the box score of the game the card is sitting next to — the same leakage
-- assert_player_leaders_exclude_the_current_week guards one model upstream, and it is A106's
-- `1 preceding` window that this object inherits.
--
-- ⚠️ COMPARED ON (season_type_ordinal, week), NEVER week ALONE. Postseason week numbers restart at
-- 1, so a bowl game compared on `week <` would read as preceding an October fixture. The ordinal is
-- carried on fct_player_usage_game precisely so this comparison needs no extra join — A106's
-- version had to reach for dim_team_week and earned a `full_refresh_only` tag for it.
select
    game_id,
    team_id,
    player_id,
    player_name,
    week       as leader_week,
    usage_week,
    usage_game_id,
    'a mark must come from a game BEFORE the one it is shown beside' as rule
from {{ ref('srv_game_team_leader_usage') }}
where (usage_season_type_ordinal, usage_week) >= (season_type_ordinal, week)
