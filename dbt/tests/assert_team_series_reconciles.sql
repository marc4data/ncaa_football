{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only`, AND IT IS THE SEVENTH TEST TO NEED IT.
--
-- `cfbd_scores_refresh` rebuilds `srv_game` and its ancestors every two hours. It does NOT
-- rebuild `fct_team_series` — verified against the compiled manifest, not assumed. So the
-- second half of this test compares a view that advances with every completed game against a
-- fact that only moves on the weekly build, and the gap it measures is the interval between
-- two refreshes rather than a defect.
--
-- IT BROKE ON 2026-09-04 AND TOOK THE SITE'S FRESHNESS WITH IT. `publish_to_serving` sits
-- downstream of `dbt_test` on the default all_success rule, so three consecutive runs — 02:00,
-- 04:00, 06:00, all retries exhausted — left the serving database untouched. The only reason
-- the site was not eight hours stale is that a deploy happened to publish by hand.
--
-- SATURDAY IS WHY THIS MATTERED NOW. It started failing after the first games of the week
-- completed. A November Saturday settles ~298 games, so every one of the day's twelve runs
-- would have failed and the site would not have updated from morning to midnight.
--
-- Full authority still applies on the weekly `+tag:production` build, which refreshes both
-- sides and where a genuine disagreement is a genuine defect.
--
-- The series must add up, and must agree with the view the site already serves.
--
-- fct_team_series derives the head-to-head record from the game spine instead of fetching
-- /teams/matchup — 1,463 calls saved. The whole case for that rests on the derivation being
-- right, so it is checked two ways rather than asserted.
--
-- 1. WINS + WINS + TIES = GAMES. srv_game's first version derived one side as
--    games - home_wins, which is only correct in a sport without draws. College football had
--    no overtime before 1996 and 2,600 tied games are on record; that error overstated one
--    side in 40,045 of 102,985 rows and was invisible on screen, because a head-to-head
--    record is exactly the figure nobody arrives already knowing.
--
-- 2. IT AGREES WITH srv_game. Two independent derivations of the same fact from the same
--    spine — one per game, one per pair. They must match on the pair's most recent completed
--    meeting; where they do not, one of them is wrong and this says which pair to look at.
with arithmetic as (
    select
        'sum' as check_name,
        team_a || ' v ' || team_b as pair,
        games, team_a_wins + team_b_wins + ties as accounted
    from {{ ref('fct_team_series') }}
    where team_a_wins + team_b_wins + ties <> games
),

-- srv_game counts from the HOME team's perspective of each game, and carries the series
-- as it stood BEFORE that game. So its latest completed row plus that game's own result is
-- the all-time series.
against_serving as (
    select
        'srv_game' as check_name,
        m.home_team || ' v ' || m.away_team as pair,
        s.games + s.unscored_games,
        m.series_games + 1 as accounted
    from (
        select *, row_number() over (
                    partition by least(home_team_id, away_team_id),
                                 greatest(home_team_id, away_team_id)
                    order by season desc, game_id desc) as recency
        from {{ ref('srv_game') }}
        -- `is_completed`, NOT "points are not null" — which is what this test said first and
        -- was wrong about. A cancelled game carries 0-0, not null: the 2023 Wheeling v
        -- Alderson-Broaddus fixture was never played and reads 0-0 completed=false. Using
        -- points as a proxy for completion counted it, and the test reported five failures
        -- against a model that was right. The model uses is_completed; so must this.
        where is_completed
    ) m
    join {{ ref('fct_team_series') }} s
      on s.team_a_id = least(m.home_team_id, m.away_team_id)
     and s.team_b_id = greatest(m.home_team_id, m.away_team_id)
    where m.recency = 1
      -- games + unscored is MEETINGS, which is what srv_game counts. `games` alone is
      -- meetings with a known result, and three completed games across the whole spine have
      -- no recorded score.
      and s.games + s.unscored_games <> m.series_games + 1
)

select * from arithmetic
union all
select * from against_serving
