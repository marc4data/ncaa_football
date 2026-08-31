-- SRS with the classification column: one row per (season, team).
--
-- Identical to /ratings/srs plus `classification` (fbs / fcs / ii / iii), which is the field
-- that makes the wider team coverage usable — without it, "265 SRS rows against 134 Elo rows"
-- is a mystery rather than a filter. Kept as its own model rather than folded into
-- stg_rating_srs because they are separate endpoints with separate raw tables, and a staging
-- model that silently merged two endpoints would make the coverage matrix lie about both.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_srs_expanded') }}
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
                order by {{ json_get_string('row_json', 'conference') }} nulls last,
                         filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)    as season,
    {{ json_get_string('row_json', 'team') }}                 as team,
    {{ json_get_string('row_json', 'classification') }}       as classification,
    {{ json_get_string('row_json', 'conference') }}           as conference,
    {{ json_get_string('row_json', 'division') }}             as division,
    cast({{ json_get_string('row_json', 'ranking') }} as int) as ranking,
    {{ safe_numeric(json_get_string('row_json', 'rating')) }} as rating
from deduped
