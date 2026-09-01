-- The play-stat type vocabulary: one row per type. 26 of them.
--
-- The controlled list behind stg_play_stat.stat_type. Two fields, and the smaller sibling of
-- stg_play_type — note the key is `name` here where the play types use `text`, and there is
-- no abbreviation. Two vocabularies from one API, spelled two ways.

with successful_fetches as (

    select
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_plays_stats_types') }}
    where status_code = 200

),

exploded as (

    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'id') }} as int) as stat_type_id,
    -- `name` here; the play-type vocabulary calls the same concept `text`.
    {{ json_get_string('row_json', 'name') }}            as stat_type
from exploded
