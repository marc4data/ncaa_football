-- Team recruiting class ranking: one row per (class year, team). Four fields, all carried.
--
-- `rank` IS THE NATIONAL RANK OF THE CLASS and `points` is the composite score it was ranked
-- on. The two disagree on ties — several teams can share a points total and get distinct
-- ranks — so a leaderboard built on rank and one built on points are not interchangeable.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_recruiting_teams') }}
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
    cast({{ json_get_string('row_json', 'year') }} as int)  as recruiting_class,
    {{ json_get_string('row_json', 'team') }}               as team,
    cast({{ json_get_string('row_json', 'rank') }} as int)  as national_rank,
    {{ safe_numeric(json_get_string('row_json', 'points')) }} as points
from deduped
