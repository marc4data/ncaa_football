-- The play type vocabulary: one row per type. 49 of them.
--
-- The controlled list behind stg_play.play_type, which stores the `text` form ("Pass
-- Reception", "Rush"). Without this, validating those values means hardcoding a list that
-- goes stale whenever CFBD adds a type — and it has 49, several of which appear only in
-- unusual games.
--
-- Carries an `id` and an `abbreviation` that stg_play does NOT store, so this is also the
-- only way to get either from a play.

with successful_fetches as (

    select
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_plays_types') }}
    where status_code = 200

),

exploded as (

    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'id') }} as int) as play_type_id,
    -- The form stg_play.play_type actually stores.
    {{ json_get_string('row_json', 'text') }}            as play_type,
    {{ json_get_string('row_json', 'abbreviation') }}    as abbreviation
from exploded
