-- CFBD's own "core" rating: one row per (season, team), AS OF a point in the season.
--
-- THE GRAIN IS NOT (season, team). It is (season, team, through_season_type, through_week) —
-- this endpoint publishes the rating as it stood through a given week, so a full backfill
-- accumulates a time series rather than one row per team. The landed data holds a single
-- as-of point per season today, which is exactly the condition under which a (season, team)
-- assumption looks correct and silently starts dropping rows later.
--
-- So the dedup partitions on all four, and the grain sweep declares all four. If CFBD only
-- ever serves one as-of point per season the extra keys cost nothing; if it serves more, the
-- model keeps them instead of arbitrarily keeping one.
--
-- `modelVersion` is carried because a rating is not comparable across model versions, and a
-- chart that silently splices core-v1 and core-v2 would show a step change that is an
-- artifact rather than a result.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_core') }}
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
                    {{ json_get_string('row_json', 'team') }},
                    {{ json_get_string('row_json', 'throughSeasonType') }},
                    {{ json_get_string('row_json', 'throughWeek') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)         as season,
    {{ json_get_string('row_json', 'throughSeasonType') }}         as through_season_type,
    cast({{ json_get_string('row_json', 'throughWeek') }} as int)  as through_week,
    {{ json_get_string('row_json', 'team') }}                      as team,
    {{ json_get_string('row_json', 'conference') }}                as conference,
    {{ safe_numeric(json_get_string('row_json', 'overall')) }}     as overall,
    {{ safe_numeric(json_get_string('row_json', 'offense')) }}     as offense,
    {{ safe_numeric(json_get_string('row_json', 'defense')) }}     as defense,
    cast({{ json_get_string('row_json', 'offensePlays') }} as int) as offense_plays,
    cast({{ json_get_string('row_json', 'defensePlays') }} as int) as defense_plays,
    {{ json_get_string('row_json', 'modelVersion') }}              as model_version
from deduped
