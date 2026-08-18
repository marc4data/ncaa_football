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
        {{ json_get_string('team', 'homeAway') }}            as home_away,
        cast({{ json_get_string('team', 'points') }} as int) as points,
        {{ json_array_elements(json_get_object('team', 'stats')) }} as stat
    from team_rows

)

select
    game_id,
    team_id,
    home_away,
    points,
    {{ json_get_string('stat', 'category') }} as stat_category,
    {{ json_get_string('stat', 'stat') }}     as stat_raw
from stat_rows
