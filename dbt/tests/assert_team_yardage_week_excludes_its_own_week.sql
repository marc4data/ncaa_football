{{ config(tags=['full_refresh_only']) }}
-- ⚠️ TAGGED `full_refresh_only`: EXCLUDED FROM cfbd_scores_refresh, WHICH REBUILDS ONE SIDE
-- OF THIS COMPARISON AND NOT THE OTHER.
--
-- The gated DAGs rebuild srv_game, srv_team_game_log, srv_game_weather and the two
-- distribution views, plus their ancestors — which includes fct_game_team and dim_team_week,
-- both read below. It does NOT rebuild fct_team_yardage_week. So after a two-hourly refresh
-- the inputs have moved and the model has not, this test fails for a reason the DAG cannot
-- fix, and publish_to_serving — downstream on all_success — stops updating the site at all.
--
-- That is R-226 exactly: on 2026-09-04 assert_team_series_reconciles failed three consecutive
-- runs and the site was fresh only because a deploy happened to publish by hand. This is the
-- ninth instance of the shape, and it was caught by the guard rather than by an outage —
-- tests/test_dag_structure.py failed the moment this test was written, which is the whole
-- reason that check is a pytest wrapper and not only a CI step.
--
-- The check is a full-build consistency assertion by nature: it compares a cumulative model
-- against the games it accumulates, which is only a coherent question once both have been
-- built from the same data.

-- THE OFF-BY-ONE, CHECKED BY ARITHMETIC RATHER THAN BY READING THE SQL. R-476.
--
-- fct_team_yardage_week's row for week N is cumulative over completed games in weeks strictly
-- BEFORE N. The window frame ends at `1 preceding`, not `current row`, and that single word is
-- the difference between a correct column and one that looks right on every row except the
-- ones anyone checks — a Week 5 matchup showing a yardage average that already contains the
-- Week 5 game.
--
-- ⚠️ THIS TEST EXISTS TO FAIL IF THAT WORD CHANGES, and it was seen doing so: with
-- `current row` in the frame it returns 6,004 failing rows (measured 2026-09-09, A075). A
-- test that would pass either way is not a test, which is the whole reason it is written as
-- an equality against an independently computed sum rather than as a bound.
--
-- 6,004 rather than a bigger number because most team-weeks are unaffected either way: a bye
-- week has no game to leak in, and week 1 has nothing before it. The rows that move are
-- exactly the team-weeks where the team PLAYED that week and had already played — which is
-- the population every matchup page draws from, and is why the defect would have been
-- invisible in a spot check of a random row.
--
-- THE INDEPENDENT SUM. For each row, add up that team's completed-and-counted game yardage
-- across every EARLIER slot in the season's own chronology — earlier by
-- (season_type_ordinal, week), never by week alone, because postseason week numbers restart
-- at 1. If the model's figure and this sum disagree, the frame is wrong.
--
-- ONLY ROWS WITH SOMETHING TO CHECK. Where games_counted is 0 the model publishes null by
-- design (0 yards is a measurement a team that has not played did not make), so those rows
-- carry no arithmetic to verify and are excluded rather than coalesced into a false equality.
with counted_games as (

    -- The same "both sides of the box score are held" rule the model counts on. Stated again
    -- here rather than imported: a test that reuses the model's own definition of what counts
    -- cannot detect the model redefining it.
    select
        g.season,
        g.season_type,
        g.week,
        g.team_id,
        g.total_yards as yards_for
    from {{ ref('fct_game_team') }} g
    join {{ ref('fct_game_team') }} o
        on  o.game_id = g.game_id
        and o.team_id = g.opponent_team_id
    where g.is_completed
      and g.team_id is not null
      and g.opponent_team_id is not null
      and g.total_yards is not null
      and o.total_yards is not null

),

ordinals as (

    select distinct season, season_type, week, season_type_ordinal
    from {{ ref('dim_team_week') }}

),

expected as (

    select
        y.season, y.season_type, y.week, y.team_id,
        y.total_yards_for   as model_yards,
        y.games_counted     as model_games,
        coalesce(sum(c.yards_for), 0) as expected_yards,
        count(c.yards_for)            as expected_games
    from {{ ref('fct_team_yardage_week') }} y
    left join counted_games c
        on  c.season  = y.season
        and c.team_id = y.team_id
    left join ordinals co
        on  co.season      = c.season
        and co.season_type = c.season_type
        and co.week        = c.week
        -- STRICTLY EARLIER in the season's chronology. This is the assertion.
        and (co.season_type_ordinal, co.week) < (y.season_type_ordinal, y.week)
    where y.games_counted > 0
      and (c.season is null or co.season is not null)
    group by y.season, y.season_type, y.week, y.team_id,
             y.total_yards_for, y.games_counted

)

select *
from expected
where model_yards != expected_yards
   or model_games != expected_games
