-- Players page: game log, one row per player x game x category x stat type.
--
-- 2024+ only, because box scores are `recent` scope. A player with a 2015 season on the
-- season tab and nothing here is the honest state, not a defect — srv_player_stats runs
-- back to 2004 and this cannot.
--
-- Narrower than the fact on purpose; see srv_player_stats for why serving columns are
-- rationed rather than copied.
select
    g.player_game_stat_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.game_date,
    g.start_date,
    g.player_id,
    g.player_slug,
    g.player_name,
    g.team,
    g.team_id,
    g.conference,
    g.home_away,
    g.opponent,
    g.opponent_team_id,
    g.team_points,
    g.stat_category,
    g.stat_type,
    g.stat_raw,
    g.stat_value,
    g.stat_made,
    g.stat_attempted,
    ao.as_of_ts
from {{ ref('fct_player_game_stat') }} g
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
