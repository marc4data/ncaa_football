-- The playoff bracket header: one row per (season, competition).
--
-- THE PAYLOAD IS A SINGLE OBJECT, NOT AN ARRAY — the only endpoint in the project shaped that
-- way. So there is no json_array_elements here; the response body IS the row.
--
-- DELIBERATELY PARTIAL, AND THIS IS THE ONE PLACE IN THE STAGING LAYER THAT IS TRUE.
-- /playoffs/cfp is a COMPOSITE: it carries `participants[]`, which is byte-for-byte what
-- /playoffs/cfp/participants serves, and `rounds[].matchups[]`, which is what
-- /playoffs/cfp/games serves. Both have dedicated endpoints, dedicated raw tables and
-- dedicated models — stg_cfp_participant and stg_cfp_matchup.
--
-- Unnesting them here as well would put the same rows in two places from two sources that
-- can drift apart between fetches, and there would be no way to say which was right. The
-- coverage matrix reports /playoffs/cfp as partial as a result, and that is the honest
-- reading: the fields are exposed, from the endpoints that own them.
--
-- What only this endpoint has is the bracket's own shape — the format, the field size, the
-- status and the champion — and that is what this model holds.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as bracket,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_playoffs_cfp') }}
    where status_code = 200

)

select
    cast({{ json_get_string('bracket', 'season') }} as int)    as season,
    {{ json_get_string('bracket', 'competition') }}            as competition,
    -- e.g. `twelve_team_2024`. The format changed in 2024 and will change again; a bracket
    -- read without it cannot be compared across eras.
    {{ json_get_string('bracket', 'format') }}                 as format,
    cast({{ json_get_string('bracket', 'teamCount') }} as int) as team_count,
    {{ json_get_string('bracket', 'status') }}                 as status,
    cast({{ json_get_nested_string('bracket', ['champion', 'id']) }} as int)
                                                               as champion_team_id,
    {{ json_get_nested_string('bracket', ['champion', 'school']) }}     as champion_school,
    {{ json_get_nested_string('bracket', ['champion', 'conference']) }} as champion_conference
from successful_fetches
where recency = 1
