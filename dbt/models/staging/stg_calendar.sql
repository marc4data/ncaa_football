-- One row per (season, season_type, week) — the week boundaries CFBD publishes.
--
-- CFBD serves no calendar before 2002 (probed 2026-08-15). That floor is a real constraint
-- on anything joined at week grain, and is asserted downstream in dim_week rather than
-- left as folklore.

with successful_fetches as (

    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_calendar') }}
    where status_code = 200

),

weeks as (

    select {{ json_array_elements('payload') }} as week
    from successful_fetches
    where recency = 1

)

select
    cast({{ json_get_string('week', 'season') }} as int) as season,
    {{ json_get_string('week', 'seasonType') }}          as season_type,
    cast({{ json_get_string('week', 'week') }} as int)   as week,
    cast({{ json_get_string('week', 'startDate') }} as {{ type_timestamp_tz() }}) as start_at,
    cast({{ json_get_string('week', 'endDate') }} as {{ type_timestamp_tz() }})   as end_at,
    cast({{ json_get_string('week', 'firstGameStart') }} as {{ type_timestamp_tz() }}) as first_game_at,
    cast({{ json_get_string('week', 'lastGameStart') }} as {{ type_timestamp_tz() }})  as last_game_at
from weeks
