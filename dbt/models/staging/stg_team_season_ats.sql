-- Against-the-spread record: one row per (season, team).
--
-- How a team performed against the betting line rather than on the scoreboard — wins,
-- losses, pushes and the average margin by which it beat the spread.
--
-- SHIPS A REAL teamId, unlike most of the season-grain endpoints, so it joins to dim_team
-- without a name match.
--
-- `games` IS NOT atsWins + atsLosses + atsPushes IN EVERY ROW. A game with no line recorded
-- counts toward `games` and toward none of the three outcomes, so the difference is the
-- number of unlined games — which is itself worth knowing and would be destroyed by
-- deriving `games` instead of carrying it.
--
-- `avgCoverMargin` is signed: positive means the team beat the spread on average.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_teams_ats') }}
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
                    {{ json_get_string('row_json', 'teamId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)      as season,
    cast({{ json_get_string('row_json', 'teamId') }} as int)    as team_id,
    {{ json_get_string('row_json', 'team') }}                   as team,
    {{ json_get_string('row_json', 'conference') }}             as conference,
    cast({{ json_get_string('row_json', 'games') }} as int)     as games,
    cast({{ json_get_string('row_json', 'atsWins') }} as int)   as ats_wins,
    cast({{ json_get_string('row_json', 'atsLosses') }} as int) as ats_losses,
    cast({{ json_get_string('row_json', 'atsPushes') }} as int) as ats_pushes,
    {{ safe_numeric(json_get_string('row_json', 'avgCoverMargin')) }} as avg_cover_margin
from deduped
