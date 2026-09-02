-- RULED OUT OF srv_game AT GAME GRAIN, DELIBERATELY. R-090, decided 2026-09-02.
--
-- This model is clean game grain (1,849 rows / 1,849 games) and folding it into the game
-- serving view is the obvious next move. It was considered and rejected on the merits, so the
-- reasoning is recorded here rather than being rediscovered:
--
--   excitement_index   is the SAME figure fct_game already carries from /games. A second
--                      copy on the same row is two columns that can disagree.
--   home_winner        is derivable from the points, and srv_game computes `winner` from
--                      them already. A stored boolean beside a derived one is a copy waiting
--                      to drift.
--   home_win_prob      is the POSTGAME number — 0.9989 for a blowout. Beside a model's
--                      prediction on a Schedule or Matchup row it would read as a forecast,
--                      and be wrong in the most confident possible way.
--
-- What /game/box/advanced is actually worth is stg_game_box_team, which is game x TEAM grain
-- and lands in srv_game_team via fct_game_team_advanced. The grain rule sent it there:
-- "Can't add game.team grain to a table that is at game grain."

-- Advanced box score, game header: one row per game.
--
-- THE GAME ID IS NOT IN THE PAYLOAD. /game/box/advanced is fetched one game at a time and
-- the response never names which game it is — the id exists only in the request, so it is
-- read from `params` exactly as stg_teams reads its season. A response whose params carry no
-- id cannot be attributed to a game and is excluded rather than guessed at.
--
-- THE RESPONSE IS A SINGLE OBJECT with three sub-structures at different grains — gameInfo
-- (this model), teams (stg_game_box_team) and players (stg_game_box_player). Three models
-- over one raw table, because one row per game, per team and per player are three different
-- things and flattening them together would multiply every game row by its roster.
--
-- `homeWinProb` HERE IS THE POSTGAME FIGURE — 0.9989 for a 63-0 win — not a pregame forecast.
-- stg_game_pregame_wp holds the forecast and stg_game_win_probability the in-game series;
-- three win probabilities from three endpoints, and only this one is retrospective.

with successful_fetches as (

    select
        filename,
        {{ json_get_string('params', 'id') }}    as game_id_raw,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'id') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_game_box_advanced') }}
    where status_code = 200
      and {{ json_get_string('params', 'id') }} is not null

)

select
    cast(game_id_raw as bigint) as game_id,
    {{ json_get_nested_string('payload', ['gameInfo', 'homeTeam']) }}   as home_team,
    cast({{ json_get_nested_string('payload', ['gameInfo', 'homePoints']) }} as int)
                                                                        as home_points,
    {{ safe_numeric(json_get_nested_string('payload', ['gameInfo', 'homeWinProb'])) }}
                                                                        as home_win_prob,
    {{ json_get_nested_string('payload', ['gameInfo', 'awayTeam']) }}   as away_team,
    cast({{ json_get_nested_string('payload', ['gameInfo', 'awayPoints']) }} as int)
                                                                        as away_points,
    {{ safe_numeric(json_get_nested_string('payload', ['gameInfo', 'awayWinProb'])) }}
                                                                        as away_win_prob,
    cast({{ json_get_nested_string('payload', ['gameInfo', 'homeWinner']) }} as boolean)
                                                                        as home_winner,
    {{ safe_numeric(json_get_nested_string('payload', ['gameInfo', 'excitement'])) }}
                                                                        as excitement_index
from successful_fetches
where recency = 1
