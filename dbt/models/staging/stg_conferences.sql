-- One row per conference per season.
--
-- Note the naming inversion in the payload: `name` is the short form ("ACC") and
-- `shortName` is the full title ("Atlantic Coast Conference"). Columns below are named for
-- what they contain, not for what CFBD calls them, because `stg_teams.conference` joins on
-- the short form and a mismatched name here would silently drop every team's conference.

with successful_fetches as (

    select
        params,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_conferences') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

conferences as (

    select season, {{ json_array_elements('payload') }} as conference
    from successful_fetches
    where recency = 1

)

select
    season,
    cast({{ json_get_string('conference', 'id') }} as int) as conference_id,
    {{ json_get_string('conference', 'name') }}            as conference_name,
    {{ json_get_string('conference', 'shortName') }}       as conference_long_name,
    {{ json_get_string('conference', 'abbreviation') }}    as conference_abbreviation,
    {{ json_get_string('conference', 'classification') }}  as classification,
    cast({{ json_get_string('conference', 'memberCount') }} as int) as member_count_reported
from conferences
