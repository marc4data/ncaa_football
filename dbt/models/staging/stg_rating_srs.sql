-- Simple Rating System: one row per (season, team). Flat, six fields, all of them carried.
--
-- SRS COVERS FAR MORE TEAMS THAN THE OTHER RATINGS — 265 rows for 2024 against 134 for Elo
-- and FPI, because it rates FCS teams too. Anything joining ratings side by side will find
-- SRS populated where the others are null, and that is the data rather than a defect.
--
-- `division` is null for every modern row and populated for older seasons; carried for the
-- same reason as SP+'s components.
--
-- DUPLICATES ARE REAL HERE. /ratings/srs returns some schools twice — once with a conference
-- and once with `conference: null`, carrying an identical rating. That produced three
-- duplicate natural keys in fct_team_rating and was fixed in stg_team_rating. The dedup below
-- partitions on (year, team) and so collapses them; which of the two rows survives is
-- arbitrary but their ratings agree, and the conference is available from dim_team anyway.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_srs') }}
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
                -- Prefer the row that names a conference; see the header. `nulls last`
                -- makes that explicit rather than leaving it to the file order.
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
    {{ json_get_string('row_json', 'conference') }}           as conference,
    {{ json_get_string('row_json', 'division') }}             as division,
    cast({{ json_get_string('row_json', 'ranking') }} as int) as ranking,
    {{ safe_numeric(json_get_string('row_json', 'rating')) }} as rating
from deduped
