-- Advanced box score, player grain: one row per (game, player). Usage and PPA side by side.
--
-- TWO BLOCKS KEYED BY PLAYER NAME, joined the same way and for the same reason as the team
-- blocks: `players.usage` and `players.ppa` are separate arrays with no positional guarantee.
--
-- NO ATHLETE ID ON THIS PAYLOAD — the key is the player's NAME within the game, which is why
-- the grain includes the team as well. Two players with the same name in one game would
-- collide, and there is nothing in the response that could separate them; /games/players and
-- /stats/player/season both carry real ids and are the better join for anything player-level.
-- This model is for the advanced metrics the other two do not have.
--
-- USAGE IS A SHARE AND PPA IS A RATE. `usage_total` of 0.042 means 4.2% of the team's plays;
-- `ppa_average_total` of -0.578 is points per play. Both are small decimals and neither is
-- the other.

{% set usage_splits = ['total', 'quarter1', 'quarter2', 'quarter3', 'quarter4',
                       'rushing', 'passing'] %}

with responses as (

    select
        filename,
        cast({{ json_get_string('params', 'id') }} as bigint) as game_id,
        {{ json_get_object('content', 'data') }}              as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'id') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_game_box_advanced') }}
    where status_code = 200
      and {{ json_get_string('params', 'id') }} is not null

),

latest as (
    select game_id, {{ json_get_object('payload', 'players') }} as players
    from responses where recency = 1
),

{#- DEDUPED BEFORE THE JOIN, for the same reason as stg_game_box_team.
    CFBD emits the same TEAM twice inside a block in four games, which multiplied that model
    to 128 rows for one key. The exposure here is identical in shape — two blocks keyed by
    player name, joined — so a repeated player would double every row for that player.
    Cheaper to prevent than to detect: the grain sweep would catch it, but only after a
    build. #}
{% set player_blocks = ['usage', 'ppa'] %}

{%- for block in player_blocks %}
{{ block }} as (
    select game_id, b
    from (
        select
            game_id,
            b,
            row_number() over (
                partition by game_id,
                             {{ json_get_string('b', 'player') }},
                             {{ json_get_string('b', 'team') }}
            ) as copy
        from (
            select game_id, {{ json_array_elements(json_get_object('players', block)) }} as b
            from latest
        ) exploded
    ) ranked
    where copy = 1
),
{% endfor %}

spine as (
    select game_id,
           {{ json_get_string('b', 'player') }} as player_name,
           {{ json_get_string('b', 'team') }}   as team
    from usage
    union
    select game_id,
           {{ json_get_string('b', 'player') }},
           {{ json_get_string('b', 'team') }}
    from ppa
)

select
    s.game_id,
    s.player_name,
    s.team,
    coalesce({{ json_get_string('u.b', 'position') }},
             {{ json_get_string('p.b', 'position') }}) as position

{%- for split in usage_splits %},
    {{ safe_numeric(json_get_string('u.b', split)) }} as usage_{{ snake_case(split) }}
{%- endfor %}

{%- for block, prefix in [('average', 'ppa_average'), ('cumulative', 'ppa_cumulative')] %}
    {%- for split in usage_splits %},
    {{ safe_numeric(json_get_nested_string('p.b', [block, split])) }}
        as {{ prefix }}_{{ snake_case(split) }}
    {%- endfor %}
{%- endfor %}

from spine s
left join usage u
    on u.game_id = s.game_id
   and {{ json_get_string('u.b', 'player') }} = s.player_name
   and {{ json_get_string('u.b', 'team') }} = s.team
left join ppa p
    on p.game_id = s.game_id
   and {{ json_get_string('p.b', 'player') }} = s.player_name
   and {{ json_get_string('p.b', 'team') }} = s.team
