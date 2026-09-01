-- Which conference a team belonged to, and when: one row per (team, conference, start year).
--
-- THE ONLY ENDPOINT THAT DATES AN AFFILIATION. dim_team carries one conference row per team
-- per SEASON, which answers "who was in the Big 12 in 2024" and needs a row for every year.
-- This answers "when did Arizona join" in one row, with `start_year` and an `end_year` that
-- is NULL FOR A CURRENT AFFILIATION — the open interval is the useful part and coercing it to
-- a far-future date would break the `is null` test that identifies current membership.
--
-- GRAIN INCLUDES START YEAR because a team can rejoin a conference it previously left, which
-- is two intervals for the same (team, conference) pair.
--
-- Carries a conferenceId, which most conference-bearing endpoints do not — /ppa/teams,
-- /ratings/* and the rest give a name only.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_conferences_affiliations') }}
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
                    {{ json_get_string('row_json', 'teamId') }},
                    {{ json_get_string('row_json', 'conferenceId') }},
                    {{ json_get_string('row_json', 'startYear') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'teamId') }} as int)       as team_id,
    {{ json_get_string('row_json', 'team') }}                      as team,
    cast({{ json_get_string('row_json', 'conferenceId') }} as int) as conference_id,
    {{ json_get_string('row_json', 'conference') }}                as conference,
    {{ json_get_string('row_json', 'conferenceAbbreviation') }}    as conference_abbreviation,
    {{ json_get_string('row_json', 'classification') }}            as classification,
    {{ json_get_string('row_json', 'conferenceDivision') }}        as conference_division,
    cast({{ json_get_string('row_json', 'startYear') }} as int)    as start_year,
    -- Null means CURRENT. See the header.
    cast({{ json_get_string('row_json', 'endYear') }} as int)      as end_year
from deduped
