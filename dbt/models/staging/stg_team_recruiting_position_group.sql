-- Recruiting strength by position group: one row per (team, position group).
--
-- THIS MODEL HAS NO UNIQUE KEY, AND THAT IS THE ENDPOINT'S DOING RATHER THAN THE MODEL'S.
--
-- Every specific position group — Defensive Back, Quarterback, Special Teams and the rest —
-- is exactly one row per team. But `All Positions` appears EIGHT TIMES for 241 of the 264
-- teams, with DIFFERENT ratings and commit counts on each row and NOTHING in the payload to
-- tell them apart: same team, same conference, same positionGroup string.
--
-- Alabama's eight carry 79, 95, 58, 79, 28, 83, 45 and 39 commits. They are clearly slices of
-- something — recruit type, or a year window — but the response returns neither, so the
-- distinction exists upstream and is discarded before it reaches us.
--
-- WHY THE FETCH IS PART OF THE PROBLEM. /recruiting/groups accepts startYear, endYear,
-- recruitType, team and conference, and defaults to 2000-present with recruitType
-- HighSchool. The registry calls it with NO parameters, so the window is implicit and is not
-- echoed back. Fetching explicitly per window would put the discriminator in `params` where
-- the model could read it — that is a registry change, recorded in the decision log rather
-- than done here.
--
-- Until then this model is deliberately EXEMPT from the grain sweep and carries no unique
-- test. Declaring (team, position_group) unique would fail on every build; inventing a row
-- number to make it pass would manufacture a key out of file ordering, which is worse than
-- having none.
--
-- NOT A SEASON, EITHER. There is no year column, so this cannot be joined to
-- stg_team_recruiting_rank on a class.
--
-- `commits` AND `averageStars` ARRIVE AS STRINGS — "4" and "2.5000000000000000" — where
-- `averageRating` and `totalRating` arrive as numbers, in the same object. safe_numeric
-- absorbs both; a hard cast on the two string columns works today and breaks on the first
-- empty string.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload,
        -- The endpoint takes no parameters, so there is nothing to partition on: the newest
        -- fetch of the one all-time answer wins outright.
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_recruiting_groups') }}
    where status_code = 200

),

exploded as (

    select {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    {{ json_get_string('row_json', 'team') }}          as team,
    {{ json_get_string('row_json', 'conference') }}    as conference,
    {{ json_get_string('row_json', 'positionGroup') }} as position_group,
    {{ safe_numeric(json_get_string('row_json', 'averageRating')) }} as average_rating,
    {{ safe_numeric(json_get_string('row_json', 'totalRating')) }}   as total_rating,
    -- Strings on the wire; see the header.
    {{ safe_numeric(json_get_string('row_json', 'commits')) }}       as commits,
    {{ safe_numeric(json_get_string('row_json', 'averageStars')) }}  as average_stars
from exploded
