{{ config(materialized='table') }}

-- The all-time head-to-head record between two teams: one row per unordered pair.
--
-- BUILT FROM THE GAME SPINE, NOT FETCHED. /teams/matchup returns exactly this, and pulling
-- it would have cost 1,463 calls for data the warehouse already holds. Verified before the
-- decision rather than after: the derivation reproduces the endpoint exactly for
-- Alabama-Auburn — 84 games, 51-32-1, 1902 to 2025 — and the only apparent discrepancy, 85
-- games in the spine against 84 from the API, is the 2026 fixture that has not been played.
--
-- It is also better than the endpoint in two ways that matter here. The join is on TEAM IDS,
-- where /teams/matchup takes and returns names; and it covers every pair that has ever
-- played, where the endpoint answers one pair per call.
--
-- WHY IT EXISTS WHEN srv_game ALREADY COMPUTES A SERIES. That one is per GAME — the
-- series as it stood before each meeting, which is what a matchup page wants. Asking "what
-- is the all-time record between these two" of that view means knowing to pick their most
-- recent game. This is the same fact at the grain a question about a rivalry actually has,
-- which is the difference between the site's needs and the warehouse's.
--
-- THE PAIR IS UNORDERED AND THAT IS THE WHOLE MODELLING PROBLEM. A series has no home team,
-- so (Alabama, Auburn) and (Auburn, Alabama) must be one row. Ordering the pair by team id
-- makes `team_a` the lower id — arbitrary but stable, and stable is what a join needs.
-- Wins are then counted for each side explicitly rather than one side being derived.
--
-- A TIE IS ITS OWN OUTCOME. srv_game's first version derived the away record as
-- games - home_wins, which is only correct in a sport without draws; college football had no
-- overtime before 1996 and 2,600 tied games are on record, so that overstated one side in
-- 40,045 of 102,985 rows. Both sides and the ties are counted here, and the three sum to
-- the game count — asserted in the test rather than trusted.
--
-- COMPLETED GAMES ONLY. A scheduled fixture has no winner, and counting it would make every
-- upcoming rivalry game shift the record it is about to change. Note that a cancelled game
-- reads 0-0 with is_completed FALSE rather than null points, so completion is the criterion
-- and the score is not a proxy for it.
--
-- AND THREE COMPLETED GAMES HAVE NO RECORDED SCORE. Sul Ross State v Angelo State in 2025 is
-- one: completed, away 62, home null. Upstream data, not ours. They cannot be credited to
-- either side without inventing a result, so they are excluded from the win tally — but
-- counted in `unscored_games` rather than silently dropped, because "this rivalry has an
-- unresolved meeting" is a fact about the series and a disappearing row is not.
--
-- The consequence is deliberate: `games` is games with a known result, and
-- games + unscored_games is meetings. The reconciliation test checks the second against
-- srv_game, which counts every completed game.

with played as (

    select
        game_id,
        season,
        home_team_id,
        away_team_id,
        home_points,
        away_points,
        -- Ordered pair: lower id first. Arbitrary, stable, and what makes the two
        -- orientations of one rivalry collapse to a single row.
        least(home_team_id, away_team_id)    as team_a_id,
        greatest(home_team_id, away_team_id) as team_b_id
    from {{ ref('fct_game') }}
    where is_completed
      and home_team_id is not null
      and away_team_id is not null

),

scored as (

    select
        team_a_id,
        team_b_id,
        season,
        case
            when home_team_id = team_a_id and home_points > away_points then 1
            when away_team_id = team_a_id and away_points > home_points then 1
            else 0
        end as team_a_won,
        case
            when home_team_id = team_b_id and home_points > away_points then 1
            when away_team_id = team_b_id and away_points > home_points then 1
            else 0
        end as team_b_won,
        case when home_points = away_points then 1 else 0 end as was_tied,
        case when home_points is null or away_points is null then 1 else 0 end as unscored
    from played

),

series as (

    select
        team_a_id,
        team_b_id,
        count(*) - sum(unscored) as games,
        sum(team_a_won)   as team_a_wins,
        sum(team_b_won)   as team_b_wins,
        sum(was_tied)     as ties,
        sum(unscored)     as unscored_games,
        min(season)       as first_season,
        max(season)       as last_season
    from scored
    group by team_a_id, team_b_id

)

select
    {{ surrogate_key(['s.team_a_id', 's.team_b_id']) }} as team_series_sk,
    s.team_a_id,
    a.school as team_a,
    s.team_b_id,
    b.school as team_b,
    s.games,
    s.team_a_wins,
    s.team_b_wins,
    s.ties,
    -- Completed meetings with no recorded score: three exist across the whole spine. Not
    -- credited to either side, not hidden either.
    s.unscored_games,
    s.first_season,
    s.last_season
from series s
-- dim_team is season-scoped, so a plain join would multiply the series by every season each
-- team existed. The name is taken from the team's MOST RECENT season, which is the one a
-- reader means by "who is this".
left join (
    select team_id, school
    from (
        select team_id, school,
               row_number() over (partition by team_id order by season desc) as recency
        from {{ ref('dim_team') }}
    ) ranked
    where recency = 1
) a on a.team_id = s.team_a_id
left join (
    select team_id, school
    from (
        select team_id, school,
               row_number() over (partition by team_id order by season desc) as recency
        from {{ ref('dim_team') }}
    ) ranked
    where recency = 1
) b on b.team_id = s.team_b_id
