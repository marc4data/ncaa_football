-- Realignment moves: one row per (team, effective year). Where a team came from and went to.
--
-- THE EVENT VIEW OF WHAT stg_conference_affiliation HOLDS AS INTERVALS. Both are worth
-- having: an interval answers "who was in the Big 12 in 2024", an event answers "who moved in
-- 2024 and from where", and deriving either from the other is a self-join nobody should have
-- to write twice.
--
-- IT ALSO CARRIES CLASSIFICATION ON BOTH SIDES, which is the only place a division move —
-- fcs to fbs — is visible as a single fact rather than as two affiliation rows that happen
-- to differ.
--
-- This is why conference membership is resolved PER SEASON everywhere else in the project:
-- 36 moves in 2024 alone, and the Big 12 went from 14 members to 16.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_conferences_changes') }}
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
                    {{ json_get_string('row_json', 'effectiveYear') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'teamId') }} as int)        as team_id,
    {{ json_get_string('row_json', 'team') }}                       as team,
    cast({{ json_get_string('row_json', 'effectiveYear') }} as int) as effective_year,

    cast({{ json_get_string('row_json', 'fromConferenceId') }} as int) as from_conference_id,
    {{ json_get_string('row_json', 'fromConference') }}                as from_conference,
    {{ json_get_string('row_json', 'fromConferenceAbbreviation') }}    as from_conference_abbreviation,
    {{ json_get_string('row_json', 'fromClassification') }}            as from_classification,

    cast({{ json_get_string('row_json', 'toConferenceId') }} as int)   as to_conference_id,
    {{ json_get_string('row_json', 'toConference') }}                  as to_conference,
    {{ json_get_string('row_json', 'toConferenceAbbreviation') }}      as to_conference_abbreviation,
    {{ json_get_string('row_json', 'toClassification') }}              as to_classification
from deduped
