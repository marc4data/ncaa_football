-- Team talent composite: one row per (season, team). Three fields.
--
-- The sum of the recruiting ratings of everyone on the roster — a rough measure of how much
-- blue-chip talent a team has accumulated, distinct from how it played. Pairs with
-- stg_team_recruiting_rank, which measures one class rather than the accumulated roster.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_talent') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'year') }},
                    {{ json_get_string('row_json', 'team') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)    as season,
    {{ json_get_string('row_json', 'team') }}                 as team,
    {{ safe_numeric(json_get_string('row_json', 'talent')) }} as talent
from deduped
