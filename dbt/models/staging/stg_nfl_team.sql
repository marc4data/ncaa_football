-- The NFL franchise list: one row per team. Four fields.
--
-- NO ID ON THIS PAYLOAD, AND THE OBVIOUS JOIN IS AMBIGUOUS RATHER THAN MERELY FRAGILE.
--
-- /draft/picks carries `nflTeamId`; this reference table carries no id at all. The only
-- shared value is the location string — /draft/picks stores `nflTeam` as "Chicago" while
-- this table has nickname "Bears" and displayName "Chicago Bears".
--
-- That join CANNOT WORK for four franchises. Verified against the real data: two teams share
-- "New York" (Jets, Giants) and two share "Los Angeles" (Rams, Chargers), and /draft/picks
-- stores exactly those bare locations. A pick assigned to New York cannot be resolved to a
-- franchise through this table at all — the information is not present, and a join would
-- silently double every such pick.
--
-- So `location` is NOT the key: `display_name` is. Anything needing the franchise behind a
-- draft pick must use `nfl_team_id` from stg_draft_pick and a mapping this endpoint does not
-- provide. Recorded rather than worked around; inventing an id here would be inventing data.

with successful_fetches as (

    select
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_draft_teams') }}
    where status_code = 200

),

exploded as (

    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    -- Matches /draft/picks.nfl_team, but NOT uniquely — see the header. Two franchises
    -- share New York and two share Los Angeles.
    {{ json_get_string('row_json', 'location') }}    as location,
    {{ json_get_string('row_json', 'nickname') }}    as nickname,
    {{ json_get_string('row_json', 'displayName') }} as display_name,
    {{ json_get_string('row_json', 'logo') }}        as logo_url
from exploded
