-- The NFL draft position vocabulary: one row per position. Two fields.
--
-- A reference lookup with no parameters and no season. It matters because /draft/picks
-- spells positions out in full — "Quarterback" — where the rest of the API uses the
-- abbreviation "QB". This is the table that maps between them, and without it joining draft
-- picks to any other player source means hardcoding that mapping somewhere worse.

with successful_fetches as (

    select
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_draft_positions') }}
    where status_code = 200

),

exploded as (

    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    {{ json_get_string('row_json', 'name') }}         as position_name,
    {{ json_get_string('row_json', 'abbreviation') }} as position_abbreviation
from exploded
