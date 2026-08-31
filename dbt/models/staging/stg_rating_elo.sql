-- Elo ratings: one row per (season, team). Four fields, the smallest ratings payload.
--
-- Elo is a running rating rather than a season summary — the value here is the team's rating
-- as of the end of the season fetched. There is no ranking column; ordering by elo within a
-- season produces one, and doing that in a mart is honest where inventing a `ranking` column
-- in staging would not be.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_elo') }}
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
    cast({{ json_get_string('row_json', 'year') }} as int) as season,
    {{ json_get_string('row_json', 'team') }}              as team,
    {{ json_get_string('row_json', 'conference') }}        as conference,
    {{ safe_numeric(json_get_string('row_json', 'elo')) }} as elo
from deduped
