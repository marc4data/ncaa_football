-- One row per NFL draft pick: who was taken, from where, by whom.
--
-- THE ONE PLACE THE COLLEGE AND NFL WORLDS MEET, and it carries ids for both:
-- collegeAthleteId / collegeId link back to CFBD's own universe, nflAthleteId / nflTeamId
-- point outward. All four are kept because a join in either direction needs its own.
--
-- THREE PICK NUMBERS, NOT ONE. `overall` is the pick number across the whole draft, `round`
-- is which round, and `pick` is the position WITHIN that round. Pick 1 of round 2 and
-- overall 33 are the same selection; using `pick` where `overall` was meant produces
-- thirty-two number-one picks per draft.
--
-- hometownInfo COORDINATES ARE STRINGS here ("38.8949855") where /recruiting/players sends
-- them as numbers, and the county key is `countyFips` where the recruiting endpoint calls it
-- `fipsCode`. Two endpoints, one concept, two spellings and two types — safe_numeric handles
-- the type and the column names are aligned so a caller does not have to know.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_draft_picks') }}
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
                    {{ json_get_string('row_json', 'overall') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)    as draft_year,
    cast({{ json_get_string('row_json', 'overall') }} as int) as overall_pick,
    cast({{ json_get_string('row_json', 'round') }} as int)   as round,
    cast({{ json_get_string('row_json', 'pick') }} as int)    as pick_in_round,
    {{ json_get_string('row_json', 'name') }}                 as name,
    {{ json_get_string('row_json', 'position') }}             as position,

    cast({{ json_get_string('row_json', 'collegeAthleteId') }} as bigint) as college_athlete_id,
    cast({{ json_get_string('row_json', 'collegeId') }} as int)           as college_team_id,
    {{ json_get_string('row_json', 'collegeTeam') }}                      as college_team,
    {{ json_get_string('row_json', 'collegeConference') }}                as college_conference,

    cast({{ json_get_string('row_json', 'nflAthleteId') }} as bigint)     as nfl_athlete_id,
    cast({{ json_get_string('row_json', 'nflTeamId') }} as int)           as nfl_team_id,
    {{ json_get_string('row_json', 'nflTeam') }}                          as nfl_team,

    cast({{ json_get_string('row_json', 'height') }} as int)  as height_inches,
    cast({{ json_get_string('row_json', 'weight') }} as int)  as weight_pounds,
    cast({{ json_get_string('row_json', 'preDraftRanking') }} as int)         as pre_draft_ranking,
    cast({{ json_get_string('row_json', 'preDraftPositionRanking') }} as int) as pre_draft_position_ranking,
    {{ safe_numeric(json_get_string('row_json', 'preDraftGrade')) }}          as pre_draft_grade,

    {{ json_get_nested_string('row_json', ['hometownInfo', 'city']) }}    as hometown_city,
    {{ json_get_nested_string('row_json', ['hometownInfo', 'state']) }}   as hometown_state,
    {{ json_get_nested_string('row_json', ['hometownInfo', 'country']) }} as hometown_country,
    -- Strings on this endpoint, numbers on /recruiting/players. See the header.
    {{ safe_numeric(json_get_nested_string('row_json', ['hometownInfo', 'latitude'])) }}
        as hometown_latitude,
    {{ safe_numeric(json_get_nested_string('row_json', ['hometownInfo', 'longitude'])) }}
        as hometown_longitude,
    -- `countyFips` here, `fipsCode` on /recruiting/players. Same concept, aligned name.
    {{ json_get_nested_string('row_json', ['hometownInfo', 'countyFips']) }}
        as hometown_fips_code
from deduped
