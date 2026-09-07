-- One row per (game, team, stat category) — the box score, long.
--
-- /games/teams returns teams[].stats as ~35 category/stat pairs per team with values as
-- STRINGS, including compound values like thirdDownEff "4-9" and possessionTime "31:24".
-- Landing long preserves every category verbatim; fct_game_team pivots a curated subset
-- into typed columns. Pivoting all 35 would mean 35 parsing decisions for categories no
-- Phase 1 page reads.

with successful_fetches as (

    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_games_teams') }}
    where status_code = 200

),

games as (

    select {{ json_array_elements('payload') }} as game
    from successful_fetches
    where recency = 1

),

team_rows as (

    select
        cast({{ json_get_string('game', 'id') }} as int) as game_id,
        {{ json_array_elements(json_get_object('game', 'teams')) }} as team
    from games

),

stat_rows as (

    select
        game_id,
        cast({{ json_get_string('team', 'teamId') }} as int) as team_id,
        -- School name and conference AS THE BOX SCORE REPORTED THEM. Both were landing and
        -- neither was read: the model took teamId and dropped the two fields next to it, so
        -- anything wanting a team name on a box score had to join out to stg_teams. That join
        -- also answers a subtly different question — stg_teams gives the season-correct
        -- affiliation, while this is what CFBD printed on this particular game. They agree
        -- almost always, and where they do not, the disagreement is the interesting part.
        {{ json_get_string('team', 'team') }}                as team,
        {{ json_get_string('team', 'conference') }}          as conference,
        {{ json_get_string('team', 'homeAway') }}            as home_away,
        cast({{ json_get_string('team', 'points') }} as int) as points,
        {{ json_array_elements(json_get_object('team', 'stats')) }} as stat
    from team_rows

)
-- ==========================================================================================
-- THE SOURCE REPEATS ENTRIES INSIDE ONE PAYLOAD, AND SOMETIMES DISAGREES WITH ITSELF (R-398).
--
-- This is what took the publish path down from 2026-09-04 to 09-07. ONE game did it:
-- 401864424, Delaware vs Merrimack, played 09-03. Its CFBD payload lists the game once and
-- carries two `teams[]` entries, correctly -- but INSIDE one team's array the same entry
-- appears twice. Merrimack: 61 stats, 29 repeated categories. Delaware: 70 stats, 35.
--
-- assert_staging_models_are_unique_on_their_grain is severity='error' and it sits in both
-- cfbd_scores_refresh.dbt_test and cfbd_lines_snapshot.dbt_test_distributions, which gate
-- publish_to_serving and publish_distributions. One malformed payload therefore froze the
-- whole site for three days across two game days.
--
-- ⚠️ MOST OF THE REPEATS ARE COPIES. SOME ARE NOT, AND THAT DISTINCTION IS THE WHOLE CARE
-- TAKEN HERE. Merrimack's firstDowns is reported as BOTH 7 AND 6 in the same array. Across
-- the two affected models: 488 of 502 player keys and 34 of 64 team keys are byte-identical
-- copies; the remaining 44 are the source giving two different answers.
--
-- Nothing in the payload adjudicates them -- no timestamp, no ordinal, no "final" marker --
-- and the score does not either. So this does NOT pretend to resolve them. It picks
-- deterministically so the grain contract holds and the pipeline runs, and it RECORDS that
-- the source disagreed, in a column, on the row. `source_value_count` > 1 is the audit
-- trail: assert_source_disagreements_stay_visible counts them, so a silent growth from 44
-- to 4,400 is a failing test rather than a quiet re-ranking of a leaderboard.
--
-- WHY max() AND NOT "the last one". Array position would be the better rule -- an appended
-- array reads as correction-wins -- but ordinality is `with ordinality` in Postgres and
-- `posexplode` in Spark, and this model must build on both. Inventing that macro during an
-- outage is a bigger change than the outage warrants. max() is arbitrary and stable; it is
-- labelled arbitrary rather than dressed up as a judgement.
-- ==========================================================================================
,

deduplicated as (

    select
        game_id, team_id, team, conference, home_away, points,
        {{ json_get_string('stat', 'category') }} as stat_category,
        max({{ json_get_string('stat', 'stat') }}) as stat_raw,
        count(distinct {{ json_get_string('stat', 'stat') }}) as source_value_count
    from stat_rows
    group by game_id, team_id, team, conference, home_away, points,
             {{ json_get_string('stat', 'category') }}

)

select
    game_id,
    team_id,
    team,
    conference,
    home_away,
    points,
    stat_category,
    stat_raw,
    source_value_count
from deduplicated
