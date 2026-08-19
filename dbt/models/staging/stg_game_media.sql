-- CFBD /games/media — which outlet is carrying a game.
--
-- One row per game per media type: a game on both TV and a streaming service appears twice,
-- so a consumer wanting "the network" must pick a type rather than assume uniqueness.
with successful_fetches as (
    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_games_media') }}
    where status_code = 200
),
media as (
    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1
)
select
    cast({{ json_get_string('row_json', 'id') }} as bigint)   as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)  as season,
    cast({{ json_get_string('row_json', 'week') }} as int)    as week,
    {{ json_get_string('row_json', 'seasonType') }}           as season_type,
    {{ json_get_string('row_json', 'mediaType') }}            as media_type,
    {{ json_get_string('row_json', 'outlet') }}               as outlet
from media
