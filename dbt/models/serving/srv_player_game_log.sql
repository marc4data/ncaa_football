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
    -- 🚨 THE RATE IS COMPUTED HERE BECAUSE §4.2 SAYS THE PAGE MAY NOT. R-611.
    --
    -- `players.py:_value` rendered `f"{int(made)}/{int(attempted)} ({made / attempted * 100:.0f}%)"`
    -- — arithmetic BETWEEN TWO COLUMNS, done in the app. Cowork's ruling, which B accepted without
    -- re-litigating: scaling ONE column by a constant for display is rendering; dividing one
    -- column by another is a metric, and metrics live upstream.
    --
    -- ⚠️ CARRIED AS A FRACTION RATHER THAN A PERCENTAGE, so the page's remaining `* 100` is the
    -- permitted kind of arithmetic — one column, one constant, for display. It also matches every
    -- other share in this warehouse (`usage_total` of 0.042 is 4.2%), so nobody has to remember
    -- which of two conventions a given column follows.
    --
    -- ⚠️ NULL WHEN `stat_attempted` IS 0 OR ABSENT, never zero. A player who attempted nothing has
    -- no rate; reporting 0% would be a measurement he did not earn — the same rule that makes
    -- total_points null rather than zero for an unplayed game.
    case when g.stat_attempted is not null and g.stat_attempted <> 0
         then cast(g.stat_made as {{ dbt.type_float() }}) / g.stat_attempted
    end                                                        as stat_made_rate,
    ao.as_of_ts
from {{ ref('fct_player_game_stat') }} g
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
