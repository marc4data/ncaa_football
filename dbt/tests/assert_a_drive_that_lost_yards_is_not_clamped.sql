-- A drive can lose yards. end < start must survive into the mart unclamped and un-abs()'d,
-- because a sack-and-punt drawn as a forward bar is a lie about the game.
--
-- TWO FAILURES IN ONE TEST, and the first is the one that matters:
--
--   'none found'   no drive in the mart ends behind where it started. Either the data changed
--                  or something clamped it. Measured: 8,750 of 78,502 do, so this cannot pass
--                  vacuously — which is the failure mode the prompt asked to be ruled out.
--   'flag wrong'   is_negative_drive disagrees with the coordinates it is derived from.
select 'no negative-yardage drive exists — geometry may be clamped' as failure
from (
    select count(*) as n
    from {{ ref('fct_drive') }}
    where end_yards_from_own_goal < start_yards_from_own_goal
) probe
where probe.n = 0

union all

select 'is_negative_drive disagrees with the coordinates: ' || cast(drive_id as {{ dbt.type_string() }})
from {{ ref('fct_drive') }}
where start_yards_from_own_goal is not null
  and end_yards_from_own_goal is not null
  and is_negative_drive <> (end_yards_from_own_goal < start_yards_from_own_goal)
