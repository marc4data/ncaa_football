{{ config(materialized='table') }}

-- Each leader's participation share in the games he had played BEFORE this one, at leader x
-- earlier-game grain. R-694. The serving view attaches these rows to a fixture and adds nothing.
--
-- ⚠️ THIS IS A TABLE AND NOT A CTE FOR A MEASURED REASON, and it is A106's lesson one round later.
-- Written inline in the serving view it did not finish in ten minutes. EXPLAIN said why: the window
-- below is reached through a ROW-VALUE INEQUALITY — `(u.season_type_ordinal, u.week) <
-- (l.season_type_ordinal, l.week)` — whose selectivity Postgres cannot estimate. It guessed
-- `rows=119` against the real figure, then `rows=1` after the window, and chose a NESTED LOOP
-- against a 34,061-row sequential scan of dim_team. A real table carries real statistics and the
-- joins downstream get a sane plan.
--
-- 🚨 POINT-IN-TIME, INHERITING A106'S WINDOW RATHER THAN RE-STATING IT. The leader rows come from
-- fct_player_leader_week, whose totals are accumulated with a frame ending at `1 preceding`. The
-- usage rows attached are the games strictly before the leader row's own week, ordered on
-- (season_type_ordinal, week) — never week alone, because postseason weeks restart at 1 and a bowl
-- game would otherwise sort into October. Marc's rule: "can only include data through Week 4 in a
-- Week 5 game."
--
-- 🚨 THE PAGE MUST NOT DIVIDE (§4.2), SO THE DENOMINATOR IS A COLUMN. Usage is strongly positional
-- — measured medians: QB 0.551, RB 0.134, WR 0.058, TE 0.041 — so a circle filled against a 0-1
-- scale leaves every receiver about 6% full, indistinguishable from DID NOT PLAY, which is the one
-- thing the circles exist to show. Cowork's ruling: fill relative to THAT PLAYER'S OWN MAXIMUM in
-- the window, with the absolute share for the hover. Both are carried.
--
-- ⚠️ `usage_games_in_window` IS FOR THE SINGLE-OBSERVATION PROBLEM, B085's shape. One earlier game
-- means max = that game = a full circle, which reads as "fully involved" and means "we have one
-- data point". The page can only say so if it is told.
with joined as (

    select
        l.season,
        l.season_type,
        l.season_type_ordinal,
        l.week,
        l.team_id,
        l.panel,
        l.leader_metric,
        l.leader_rank,
        l.player_id,
        l.player_name,
        u.game_id              as usage_game_id,
        u.week                 as usage_week,
        u.season_type          as usage_season_type,
        -- Carried so nothing downstream has to rejoin dim_team_week to order these marks.
        -- ci/check_test_refresh_scope.py caught the alternative: a test that reached for the
        -- spine to recover this straddled cfbd_scores_refresh's boundary and would have blocked
        -- a game-day publish. Carrying the column removes the straddle instead of tagging it.
        u.season_type_ordinal  as usage_season_type_ordinal,
        u.box_position,
        u.usage_total,
        u.usage_rushing,
        u.usage_passing
    from {{ ref('fct_player_leader_week') }} l
    -- 🚨 THE INEQUALITY IS THE WINDOW. A usage row for the leader's OWN week would be the game the
    -- card sits beside, which is the leakage Marc's rule forbids and which staged break 3 flips.
    join {{ ref('fct_player_usage_game') }} u
      on  u.season    = l.season
      and u.team_id   = l.team_id
      and u.player_id = l.player_id
      and (u.season_type_ordinal, u.week) < (l.season_type_ordinal, l.week)

),

windowed as (

    select
        j.*,
        -- Computed over the SAME joined set the rows come from, so the denominator cannot disagree
        -- with the marks drawn against it. If a careless change let the current week in, the
        -- circles and their scale would move together and the leakage test would still catch it.
        max(j.usage_total) over (
            partition by j.season, j.team_id, j.panel, j.player_id,
                         j.season_type_ordinal, j.week)
            as usage_total_max_in_window,
        count(*) over (
            partition by j.season, j.team_id, j.panel, j.player_id,
                         j.season_type_ordinal, j.week)
            as usage_games_in_window
    from joined j

)

select * from windowed
