{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for its family's reason (R-672): it compares a serving view with
-- marts the two-hourly scores DAG does not rebuild on one cadence.
--
-- A146, cfdb-main-R-1000. FOUR LEFT JOINS ARRIVED ON `srv_player_game_log` AND NONE OF THEM MAY
-- CHANGE ITS ROW COUNT.
--
-- 🚨 THE DEFECT THIS EXISTS FOR IS A FAN-OUT, AND IT WAS ONE KEY AWAY FROM BEING SHIPPED.
-- `dim_athlete` is the obvious join — season x player — and it is **NOT UNIQUE ON THAT PAIR**:
-- 68,357 rows against 68,347 distinct `(season, player_id)`. The ten extras are MID-SEASON
-- TRANSFERS, two team rows each. Joining on the obvious key would have duplicated those players'
-- every stat row, and **every duplicated row would have held a real jersey, a real position and a
-- real team** — a leaderboard counting one player twice with nothing on screen looking wrong.
--
-- ✅ THE VIEW JOINS ON `athlete_sk`, WHICH THE FACT ALREADY CARRIES AND WHICH IS UNIQUE — 68,357
-- rows, 68,357 distinct. **The safe key was already on the table; the obvious one was wrong.**
--
-- 🚨 AND THIS TEST EARNS ITS PLACE ON THE *OTHER* DIRECTION, WHICH WAS MEASURED RATHER THAN
-- ASSUMED. Both breaks were staged and the existing grain guard only sees one of them:
--
--     break                                  rows        grain guard   this test
--     join re-keyed to (season, player_id)   +258        FAIL 258      FAIL 1
--     LEFT join becomes INNER                -121,404    **PASS**      FAIL 1
--
-- ⚠️ **AN INNER JOIN SILENTLY DELETES 8.61% OF THE VIEW AND UNIQUENESS STILL HOLDS**, because
-- uniqueness is a property of the rows that remain. 121,404 player-stat rows would vanish — every
-- player cfdb holds no athlete dimension row for — and a leaderboard would simply never show them.
-- **Nothing else in the project can see that.** The grain guard catches the duplication; only a
-- comparison against the FACT's own count catches the deletion.
--
-- ⚠️ R-760, ASKED OF THIS TEST: what would have to be wrong for it to fire? Re-keying the athlete
-- join to `(season, player_id)`; dropping a join's season or week predicate; making any of the four
-- an INNER join, which would DELETE rows rather than add them — 8.61% of them, which is the rate at
-- which cfdb holds no athlete dimension row, NOT the 11.4% jersey-null rate (a dimension row can
-- exist and carry a null jersey, so the two figures are different and only one of them is the one
-- this break moves). All four are single-line edits somebody could plausibly make, and all four
-- move this number.
with counted as (

    select
        (select count(*) from {{ ref('fct_player_game_stat') }})  as fact_rows,
        (select count(*) from {{ ref('srv_player_game_log') }})   as view_rows

)

select
    fact_rows,
    view_rows,
    view_rows - fact_rows as difference,
    case when view_rows > fact_rows
         then 'a left join fanned out — a player-stat row is counted more than once'
         else 'a join dropped rows — a LEFT join became an INNER one' end as rule
from counted
where view_rows is distinct from fact_rows
