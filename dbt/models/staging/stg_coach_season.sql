-- One row per (coach, season, team). The coaching record, unnested from /coaches.
--
-- THE PAYLOAD IS COACH-GRAIN AND THE USEFUL GRAIN IS COACH-SEASON. /coaches returns one
-- object per coach with a `seasons[]` array inside, so a coach who moved schools mid-career
-- is one object with several season rows. Flattening is the model.
--
-- TEAM IS IN THE SEASON, NOT THE COACH, and that is the reason the grain includes it. A
-- coach can appear twice in one season — an interim taking over mid-year is credited with
-- games at both schools — so (coach, season) is not unique and (coach, season, team) is.
--
-- `hireDate` BELONGS TO THE COACH, NOT THE SEASON, so it repeats on every row of that
-- coach. It is the date of their most recent hire, not the hire that started this season.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_coaches') }}
    where status_code = 200

),

coaches as (

    select filename, {{ json_array_elements('payload') }} as coach
    from successful_fetches

),

coach_seasons as (

    select
        filename,
        {{ json_get_string('coach', 'id') }}        as coach_id,
        {{ json_get_string('coach', 'firstName') }} as first_name,
        {{ json_get_string('coach', 'lastName') }}  as last_name,
        {{ json_get_string('coach', 'hireDate') }}  as hire_date_raw,
        {{ json_array_elements(json_get_object('coach', 'seasons')) }} as season_row
    from coaches

),

deduped as (

    select *
    from (
        select
            coach_seasons.*,
            row_number() over (
                partition by
                    coach_id,
                    {{ json_get_string('season_row', 'year') }},
                    {{ json_get_string('season_row', 'teamId') }}
                order by filename desc
            ) as recency
        from coach_seasons
    ) ranked
    where recency = 1

)

select
    cast(coach_id as int)                                            as coach_id,
    first_name,
    last_name,
    cast(hire_date_raw as {{ type_timestamp_tz() }})                 as hired_at,
    cast({{ json_get_string('season_row', 'year') }} as int)         as season,
    cast({{ json_get_string('season_row', 'teamId') }} as int)       as team_id,
    {{ json_get_string('season_row', 'school') }}                    as school,
    {{ json_get_string('season_row', 'conference') }}                as conference,
    cast({{ json_get_string('season_row', 'games') }} as int)        as games,
    cast({{ json_get_string('season_row', 'wins') }} as int)         as wins,
    cast({{ json_get_string('season_row', 'losses') }} as int)       as losses,
    cast({{ json_get_string('season_row', 'ties') }} as int)         as ties,
    {{ safe_numeric(json_get_string('season_row', 'winPercentage')) }} as win_percentage,
    cast({{ json_get_string('season_row', 'preseasonRank') }} as int)  as preseason_rank,
    cast({{ json_get_string('season_row', 'postseasonRank') }} as int) as postseason_rank,
    {{ safe_numeric(json_get_string('season_row', 'srs')) }}           as srs,
    {{ safe_numeric(json_get_string('season_row', 'spOverall')) }}     as sp_overall,
    {{ safe_numeric(json_get_string('season_row', 'spOffense')) }}     as sp_offense,
    {{ safe_numeric(json_get_string('season_row', 'spDefense')) }}     as sp_defense
from deduped
