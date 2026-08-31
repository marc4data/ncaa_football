-- One row per (game, team, category, stat type, athlete) — the player box score, long.
--
-- /games/players is the deepest payload CFBD serves: game -> teams[] -> categories[] ->
-- types[] -> athletes[]. Four levels of array, and the leaf carries the value. Flattening it
-- is the whole model; a row here is "in game G, team T, in the passing category, the C/ATT
-- type, athlete A recorded 12/31".
--
-- LONG, NOT PIVOTED, AND DELIBERATELY SO. The type names are open-ended and category-specific
-- — C/ATT, YDS, TD, INT, QBR, LONG, CAR, AVG, and more per category. Pivoting means enumerating
-- them, and every enumeration is a decision to silently drop whatever CFBD adds next. The same
-- reasoning as stg_game_team_stat: land every pair verbatim, let a mart pivot the subset a
-- page actually reads.
--
-- VALUES ARE STRINGS AND STAY STRINGS. `stat` is "12/31" for C/ATT, "58" for YDS, "1" for TD.
-- Parsing here would need one rule per type and would fail the model on an unrecognised one.
-- Typing happens where the type is known.
--
-- THERE IS NO TEAM ID IN THIS PAYLOAD. /games/players identifies a team by NAME only — unlike
-- /games/teams, which ships teamId. Anything joining this to a team dimension joins on a
-- string, and school names are not stable across seasons. Carried verbatim; resolving it needs
-- a season-scoped team map and belongs in a mart.
--
-- Athlete ids are strings in the spec and are left as strings. They look numeric, and casting
-- them to int would be a lossy guess about an identifier CFBD never promised is one.

with successful_fetches as (

    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_games_players') }}
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

category_rows as (

    select
        game_id,
        {{ json_get_string('team', 'team') }}                as team,
        {{ json_get_string('team', 'conference') }}          as conference,
        {{ json_get_string('team', 'homeAway') }}            as home_away,
        cast({{ json_get_string('team', 'points') }} as int) as points,
        {{ json_array_elements(json_get_object('team', 'categories')) }} as category
    from team_rows

),

type_rows as (

    select
        game_id, team, conference, home_away, points,
        {{ json_get_string('category', 'name') }} as stat_category,
        {{ json_array_elements(json_get_object('category', 'types')) }} as stat_type
    from category_rows

),

athlete_rows as (

    select
        game_id, team, conference, home_away, points, stat_category,
        {{ json_get_string('stat_type', 'name') }} as stat_type,
        {{ json_array_elements(json_get_object('stat_type', 'athletes')) }} as athlete
    from type_rows

)

select
    game_id,
    team,
    conference,
    home_away,
    points,
    stat_category,
    stat_type,
    {{ json_get_string('athlete', 'id') }}   as athlete_id,
    {{ json_get_string('athlete', 'name') }} as athlete_name,
    {{ json_get_string('athlete', 'stat') }} as stat_raw
from athlete_rows
