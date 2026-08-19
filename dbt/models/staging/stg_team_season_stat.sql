-- CFBD /stats/season, kept in its native EAV shape: one row per team, season and stat name.
--
-- Deliberately not pivoted here. The endpoint serves 63 distinct stat names and CFBD adds
-- to that list; a wide staging model would need a code change every time it did, and would
-- silently drop anything unrecognised. The long shape survives new stats for free.
--
-- `statValue` is declared `anyOf[string, number]` in the OpenAPI spec, so it is read as
-- text and cast defensively. Every one of the 177,876 values landed so far is numeric, but
-- the contract permits a string and the cast must not be what discovers that.
with successful_fetches as (
    select
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_stats_season') }}
    where status_code = 200
),
stats as (
    select {{ json_array_elements('payload') }} as stat_row
    from successful_fetches
    where recency = 1
)
select
    cast({{ json_get_string('stat_row', 'season') }} as int) as season,
    {{ json_get_string('stat_row', 'team') }}                as school,
    {{ json_get_string('stat_row', 'conference') }}          as conference_name,
    {{ json_get_string('stat_row', 'statName') }}            as stat_name,
    {{ json_get_string('stat_row', 'statValue') }}           as stat_value_raw
from stats
