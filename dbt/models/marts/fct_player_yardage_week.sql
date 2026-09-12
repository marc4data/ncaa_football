{{ config(materialized='table') }}

-- Yards by player, by week, in the three pairings Matchup's panels use. R-687.
--
-- One row per (season, season_type, week, team_id, player_id, panel). Only weeks a player
-- actually recorded yards in — the calendar walk belongs to fct_player_leader_week, which reads
-- this.
--
-- ⚠️ WHY THIS IS A TABLE AND NOT A CTE INSIDE fct_player_leader_week — MEASURED, not assumed,
-- after two builds failed to finish:
--
--   as a CTE referenced twice, MATERIALIZED       Postgres has no statistics for it, estimated
--                                                `rows=1` against ~400,000, chose nested loops
--                                                and went quadratic. Killed at 10 minutes.
--   as a CTE referenced twice, NOT MATERIALIZED   real estimates, but the three-way union over
--                                                1.27M box-score rows is then expanded on every
--                                                reference — nine sequential scans, plus the
--                                                dim_athlete join each time. Killed at 4 minutes.
--   as a TABLE (this)                            computed once, ANALYZEd, ~130k rows, and every
--                                                downstream estimate is real.
--
-- A097 lost an hour to the same class of defect and its lesson is the one that applies here: the
-- shape of the query matters more than the size of the data, and `work_mem` on this warehouse is
-- 4MB, so anything that sorts wide rows repeatedly pays for it on disk.
--
-- ⚠️ MARC'S PAIRING IS DELIBERATE AND THE `panel` COLUMN CARRIES IT. Marc, 2026-09-12: "Passing
-- will be top 3 receivers. Rushing is top 3 yards rushing, Total is the Top 3 QBs." The PASSING
-- panel is accompanied by the people who CAUGHT the passes. That is not an error to correct on a
-- later round, which is why the crossing is a value in a column rather than a sentence in a
-- comment:
--
--     panel       source
--     passing     receiving / YDS
--     rushing     rushing / YDS
--     total       passing + rushing YDS, for athletes dim_athlete lists at QB
--
-- ⚠️ BOX SCORES ARE `recent` SCOPE — 2024+, measured: passing, rushing and receiving YDS all run
-- 2024-2026 and nothing earlier exists. A 2015 game has no leaders and that is honest.
with contributions as (

    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'passing' as panel,
           s.stat_value as yards
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'receiving'
      and s.stat_type = 'YDS'
      and s.stat_value is not null
      and s.season >= 2024

    union all

    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'rushing',
           s.stat_value
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'rushing'
      and s.stat_type = 'YDS'
      and s.stat_value is not null
      and s.season >= 2024

    union all

    -- TOTAL YARDS FOR A QUARTERBACK IS PASSING PLUS RUSHING, summed by the group by below. A
    -- scrambling quarterback's rushing yards are his total offence as much as his throws are,
    -- and dropping them would rank a pocket passer above a dual-threat on equal production.
    --
    -- ⚠️ THIS IS THE ONE PANEL A MISSING ROSTER ROW COSTS A PLAYER HIS PLACE IN, because QB is
    -- established from dim_athlete.position and there is nowhere else to read it. Measured on
    -- 2026: FBS teams resolve 96.7% of their yards to an athlete row and non-FBS 0% — the 2026
    -- roster load covers 138 of 305 teams and was last refreshed 2026-08-15.
    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'total',
           s.stat_value
    from {{ ref('fct_player_game_stat') }} s
    join {{ ref('dim_athlete') }} a
      on  a.athlete_sk = s.athlete_sk
      and a.position = 'QB'
    where s.stat_category in ('passing', 'rushing')
      and s.stat_type = 'YDS'
      and s.stat_value is not null
      and s.season >= 2024

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'team_id', 'player_id', 'panel']) }}
        as player_yardage_week_sk,
    season,
    season_type,
    week,
    team_id,
    player_id,
    panel,
    min(player_name) as player_name,
    min(player_slug) as player_slug,
    min(athlete_sk)  as athlete_sk,
    sum(yards)       as week_yards
from contributions
group by season, season_type, week, team_id, player_id, panel
