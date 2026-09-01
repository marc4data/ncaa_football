-- Recruiting strength by position group: one row per (team, position group).
--
-- "ALL POSITIONS" IS NOT AN AGGREGATE. IT IS EVERY OTHER ROW, MISLABELLED.
--
-- This model had no unique key because `All Positions` appeared eight times per team for
-- 241 of 264 teams, with different values and nothing to tell the rows apart. The cause is
-- now established rather than guessed at.
--
-- Alabama's eight `All Positions` rows carry commit counts 95, 83, 79, 79, 58, 45, 39, 28 —
-- which is EXACTLY the multiset of its eight real position groups: Defensive Line 95,
-- Receiver 83, Defensive Back 79, Offensive Line 79, Linebacker 58, Running Back 45,
-- Special Teams 39, Quarterback 28. CFBD emits every row twice: once labelled with its
-- position group, once with the label overwritten as `All Positions`. There is no
-- aggregate anywhere in the payload.
--
-- That also explains the distribution — a team with five position groups gets five
-- `All Positions` rows, not eight — which no year- or recruit-type-based theory fit.
--
-- SO THEY ARE FILTERED OUT, and nothing is lost: every value in them is present, correctly
-- labelled, in the row it was copied from. With them gone, (team, position_group) is a real
-- grain and the model rejoins the uniqueness sweep.
--
-- assert_recruiting_groups_all_positions_is_still_a_duplicate fails the day CFBD fixes this
-- and starts sending a genuine total, because then the filter WOULD be dropping data.
--
-- SCOPED TO 2024 ONWARD, NOT ALL-TIME. The endpoint aggregates over startYear..endYear and
-- defaults to 2000-present; the registry now sends startYear=2024 and lets endYear default
-- to the current year, so this covers the project's seasons and stays correct next year
-- without an edit. The window is in `params`, which is where a reader can see it.

with successful_fetches as (

    select
        filename,
        -- CARRIED THROUGH BECAUSE THE FINAL SELECT NEEDS IT. `params` is a column of the
        -- raw table, not of the CTE, and referencing it downstream is a compile error —
        -- the same slip made in stg_api_usage_endpoint an hour earlier. Twice is a pattern:
        -- anything the last select reads has to be listed here.
        cast({{ json_get_string('params', 'startYear') }} as int) as from_season,
        {{ json_get_object('content', 'data') }} as payload,
        -- One window, one answer: the newest fetch wins outright. Partitioning on
        -- startYear would be right the day a second window is ever requested, and wrong
        -- today in a way nobody would notice — there is only one.
        row_number() over (order by filename desc) as recency
    from {{ source('raw', 'raw_recruiting_groups') }}
    where status_code = 200

),

exploded as (

    select from_season, {{ json_array_elements('payload') }} as row_json
    from successful_fetches
    where recency = 1

)

select
    -- The requested window, carried so a reader can see what the aggregate covers rather
    -- than having to know the registry.
    from_season,
    {{ json_get_string('row_json', 'team') }}          as team,
    {{ json_get_string('row_json', 'conference') }}    as conference,
    {{ json_get_string('row_json', 'positionGroup') }} as position_group,
    {{ safe_numeric(json_get_string('row_json', 'averageRating')) }} as average_rating,
    {{ safe_numeric(json_get_string('row_json', 'totalRating')) }}   as total_rating,
    -- Strings on the wire; see the header.
    {{ safe_numeric(json_get_string('row_json', 'commits')) }}       as commits,
    {{ safe_numeric(json_get_string('row_json', 'averageStars')) }}  as average_stars
from exploded
-- The mislabelled duplicates. See the header: every value here exists correctly labelled
-- in the row it was copied from.
where {{ json_get_string('row_json', 'positionGroup') }} <> 'All Positions'
