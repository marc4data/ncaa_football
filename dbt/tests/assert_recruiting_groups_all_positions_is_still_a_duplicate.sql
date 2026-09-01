{{ config(severity='warn') }}
-- `All Positions` from /recruiting/groups is every other row with its label overwritten.
--
-- ESTABLISHED, NOT ASSUMED. Alabama's eight `All Positions` rows carry commit counts
-- 95, 83, 79, 79, 58, 45, 39, 28 — exactly the multiset of its eight real position groups.
-- CFBD emits each row twice: once correctly labelled, once as `All Positions`. There is no
-- aggregate in the payload, and a team with five groups gets five of them, not eight.
--
-- stg_team_recruiting_position_group therefore FILTERS THEM OUT, and loses nothing: every
-- value is present, correctly labelled, in the row it was copied from.
--
-- THIS TEST EXISTS FOR THE DAY THAT STOPS BEING TRUE. If CFBD fixes the bug and starts
-- sending a genuine per-team total, the filter would begin dropping real data — silently,
-- because a row that is no longer emitted looks the same as a row that was never wanted.
-- Then the counts below stop matching and this fires.
--
-- SEVERITY WARN, NOT ERROR. An upstream fix is good news, not a broken pipeline, and it
-- should not block a game-day refresh at 20:00 on a Saturday. It needs a person to read the
-- payload again and delete the filter — a task, not an outage.
with per_team as (
    select
        {{ json_get_string('row_json', 'team') }} as team,
        {{ json_get_string('row_json', 'positionGroup') }} as position_group,
        {{ safe_numeric(json_get_string('row_json', 'commits')) }} as commits
    from (
        select {{ json_array_elements(json_get_object('content', 'data')) }} as row_json
        from {{ source('raw', 'raw_recruiting_groups') }}
        where status_code = 200
    ) exploded
),

labelled as (
    select team, count(*) as n, sum(commits) as total
    from per_team where position_group <> 'All Positions' group by team
),

all_positions as (
    select team, count(*) as n, sum(commits) as total
    from per_team where position_group = 'All Positions' group by team
)

-- One row per team where the two sides disagree — which is the day the filter is wrong.
select
    coalesce(l.team, a.team)               as team,
    l.n                                    as real_group_rows,
    a.n                                    as all_positions_rows,
    l.total                                as real_group_commits,
    a.total                                as all_positions_commits
from labelled l
full outer join all_positions a on a.team = l.team
where l.n is distinct from a.n
   or l.total is distinct from a.total
