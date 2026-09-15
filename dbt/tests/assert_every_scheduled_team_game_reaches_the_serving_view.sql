-- A138, cfdb-main-R-912. Every team-game the warehouse models must reach `srv_game_team`.
--
-- 🚨 THE GUARD BEHIND MARC'S "RESERVE A ROW FOR EVERY GAME" PROMISE. A135 built the schedule
-- strip on `srv_game_team` precisely because that relation already carries the whole calendar —
-- 5,848 unplayed 2026 regular team-games were measured in it — and B114 draws one row per
-- fixture from it. A view that quietly narrowed to PLAYED games would not error: the strip would
-- render, every number on it would be real, and October would simply be missing.
--
-- ⚠️ WHY IT IS WORTH A TEST RATHER THAN A COMMENT. `srv_game_team` carries one INNER join:
--
--     join ... fct_game_team_advanced ... a on a.game_team_sk = t.game_team_sk
--
-- and it is **the only join in that block without a left-vs-inner comment**, while three of its
-- neighbours carry one — including *"LEFT, not inner: a Division III fixture has no line and must
-- keep its row. An inner join here would silently narrow the view to games a sportsbook priced."*
-- 🚨 So the author was demonstrably thinking about this exact failure class and this one join is
-- unremarked.
--
-- ✅ IT IS NOT A DEFECT TODAY, AND THIS TEST IS NOT AN ARGUMENT THAT IT IS. Measured 2026-09-15:
-- `fct_game_team` 225,350 rows, `fct_game_team_advanced` 225,350, `srv_game_team` 225,350, and
-- **0 rows would be dropped by that join**. The advanced mart currently emits a row for every
-- scheduled team-game. ⚠️ THAT IS A PROPERTY OF TODAY'S DATA, NOT OF THE SQL — nothing makes it
-- true, which is the whole reason to assert it. Converting the join to a left join is a bigger
-- change than this test and is deliberately not made here.
--
-- 📊 AND NO EXISTING TEST COVERS IT. `assert_games_played_reconciles_to_schedule` reconciles
-- `mart_team_season_record` against `stg_games` `where is_completed and home_points is not null`
-- — a different relation and the COMPLETED half, which is exactly the half that cannot see a
-- view narrowing to completed games.
--
-- TWO CLAIMS:
--
--   1. NOTHING IS LOST. Every `game_team_sk` in `fct_game_team` reaches `srv_game_team`.
--   2. NOTHING IS DUPLICATED. The serving view stays one row per team-game — the other way a
--      join goes wrong, and the one a "missing rows" test cannot see.
with modelled as (

    select game_team_sk, season, week, team_id, game_id
    from {{ ref('fct_game_team') }}

),

published as (

    select game_team_sk, count(*) as rows_found
    from {{ ref('srv_game_team') }}
    group by game_team_sk

)

select
    m.game_team_sk,
    m.season,
    m.week,
    m.team_id,
    m.game_id,
    coalesce(p.rows_found, 0) as rows_in_serving,
    case
        when p.game_team_sk is null
            then 'a scheduled team-game never reached srv_game_team'
        else 'a team-game appears more than once in srv_game_team'
    end as rule
from modelled m
left join published p on p.game_team_sk = m.game_team_sk
where p.game_team_sk is null
   or p.rows_found > 1
