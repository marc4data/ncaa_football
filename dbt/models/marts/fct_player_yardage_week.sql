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
--
-- ⚠️ WIDENED BY A116 (R-717) FROM ONE MEASURE TO FIVE, AND THE NAME NO LONGER DESCRIBES ALL OF
-- THEM. Marc asked for three KPI slots on each player card, so this table now carries the
-- companions of the yards as well as the yards: receptions, carries, touchdowns, completions and
-- attempts. ⚠️ THE MODEL WAS NOT RENAMED, deliberately — `fct_player_leader_week`,
-- `srv_game_team_leader_through_prior_week`, two dbt tests and A107's own report all name it, and
-- §4 is forward-only: nothing already on disk is renamed. The grain is unchanged.
--
-- 🚨 EVERY MEASURE IS NULL OUTSIDE THE PANEL IT BELONGS TO, and that is a fact rather than a gap.
-- A receiver has no carries; a running back has no attempts. Null says "this measure does not
-- apply to this panel", which is exactly AC-G.11's distinction, and `fct_player_leader_week`
-- coalesces to zero ONLY inside the panel where the measure is real.
--
--     panel      yards                      receptions  carries  touchdowns          completions/attempts
--     passing    receiving YDS              receiving   —        receiving TD        —
--     rushing    rushing YDS                —           CAR      rushing TD          —
--     total      passing + rushing YDS      —           —        passing + rushing   C/ATT
--
-- 🚨 THE TOTAL PANEL'S TOUCHDOWNS ARE PASSING **PLUS RUSHING**, AND THAT IS THE ONE JUDGEMENT CALL
-- IN THE TRIO. The panel ranks TOTAL yards and this header already argues why — "a scrambling
-- quarterback's rushing yards are his total offence as much as his throws are". A passing-only
-- touchdown count beside a passing-plus-rushing yards ranking would mix two definitions of the
-- same quarterback in one card row. ⚠️ It is a LOOK call and therefore Marc's (§2.1); it is one
-- `case` branch to reverse and the report says so.
--
-- ⚠️ `C/ATT` CARRIES NO `stat_value` AT ALL — 1,187 of 1,187 rows null for 2026, by design, because
-- it is a PAIR. `stat_made` and `stat_attempted` are the parsed halves and both are 1,187 of 1,187
-- populated. So the `stat_value is not null` filter below has to make an exception for it, or the
-- quarterback trio loses its first slot silently. Measured before building, not after.
--
-- ⚠️ BOX SCORES ARE `recent` SCOPE — 2024+, measured: passing, rushing and receiving YDS all run
-- 2024-2026 and nothing earlier exists. A 2015 game has no leaders and that is honest.
with contributions as (

    -- ONE ROW PER BOX-SCORE STAT ROW, pivoted into the five measure columns. Each row feeds
    -- exactly one of them; the final group by sums them to the week grain. Keeping the branch
    -- row-level rather than pre-aggregating per game is what lets a team playing twice in one week
    -- sum correctly — A107 found 202 such duplicate keys and the fix was this grain, not a filter.
    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'passing' as panel,
           case when s.stat_type = 'YDS' then s.stat_value end as yards,
           case when s.stat_type = 'REC' then s.stat_value end as receptions,
           null::numeric                                       as carries,
           case when s.stat_type = 'TD'  then s.stat_value end as touchdowns,
           null::numeric                                       as completions,
           null::numeric                                       as attempts
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'receiving'
      and s.stat_type in ('YDS', 'REC', 'TD')
      and s.stat_value is not null
      and s.season >= 2024

    union all

    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'rushing',
           case when s.stat_type = 'YDS' then s.stat_value end,
           null::numeric,
           case when s.stat_type = 'CAR' then s.stat_value end,
           case when s.stat_type = 'TD'  then s.stat_value end,
           null::numeric,
           null::numeric
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'rushing'
      and s.stat_type in ('YDS', 'CAR', 'TD')
      and s.stat_value is not null
      and s.season >= 2024

    union all

    -- TOTAL YARDS FOR A QUARTERBACK IS PASSING PLUS RUSHING, summed by the group by below. A
    -- scrambling quarterback's rushing yards are his total offence as much as his throws are, and
    -- dropping them would rank a pocket passer above a dual-threat on equal production.
    --
    -- ⚠️ THIS IS THE ONE PANEL A MISSING ROSTER ROW COSTS A PLAYER HIS PLACE IN, because QB is
    -- established from dim_athlete.position and there is nowhere else to read it. Measured on
    -- 2026: FBS teams resolve 96.7% of their yards to an athlete row and non-FBS 0% — the 2026
    -- roster load covers 138 of 305 teams and was last refreshed 2026-08-15.
    --
    -- 🚨 AND NOTE THE `stat_value is not null` EXCEPTION FOR `C/ATT`. Without it every quarterback
    -- loses his completions and attempts, because that stat's value lives in `stat_made` and
    -- `stat_attempted` and its `stat_value` is null on all 1,187 of 2026's rows.
    select s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'total',
           case when s.stat_type = 'YDS'   then s.stat_value end,
           null::numeric,
           null::numeric,
           case when s.stat_type = 'TD'    then s.stat_value end,
           case when s.stat_type = 'C/ATT' then s.stat_made end,
           case when s.stat_type = 'C/ATT' then s.stat_attempted end
    from {{ ref('fct_player_game_stat') }} s
    join {{ ref('dim_athlete') }} a
      on  a.athlete_sk = s.athlete_sk
      and a.position = 'QB'
    where s.stat_category in ('passing', 'rushing')
      and s.stat_type in ('YDS', 'TD', 'C/ATT')
      and (s.stat_value is not null or s.stat_type = 'C/ATT')
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
    sum(yards)       as week_yards,
    -- ⚠️ NO `coalesce` HERE. sum() returns null when every input is null, which is precisely the
    -- "does not apply to this panel" signal the header describes. Coalescing to zero here would
    -- tell a reader a receiver had zero carries in a week he was never asked to run.
    sum(receptions)  as week_receptions,
    sum(carries)     as week_carries,
    sum(touchdowns)  as week_touchdowns,
    sum(completions) as week_completions,
    sum(attempts)    as week_attempts
from contributions
group by season, season_type, week, team_id, player_id, panel
-- The grain this model has always declared: only weeks a player actually recorded yards in.
-- Measured on 2026 before widening: every player-game carrying receiving or rushing YDS also
-- carries its REC/CAR and TD companions, 0 missing of 5,154 and 0 of 4,229, so this clause
-- changes no row that existed before A116 — it defends the invariant rather than altering it.
having sum(yards) is not null
