-- Drives are `recent` scope: 2024 onward, measured from the raw manifest rather than assumed.
--
-- THE MIXED SAMPLE IS THE POINT. A test over 2025 games alone passes whether or not the
-- boundary is handled at all, so this asserts BOTH sides of it:
--
--   in scope      a completed game in a drive season has drives
--   out of scope  a game before the boundary has none, and the view still carries the bounds
--                 that let the page say why
--
-- The out-of-scope half is what stops "no drives" from being indistinguishable from "the join
-- broke". fct_game holds games back to the 1800s, so the outside case is well populated.
select 'a game before the drive scope boundary has drives' as failure
from {{ ref('srv_drive') }} d
where d.season < d.drives_min_season

union all

select 'srv_drive carries no scope bounds, so an empty game cannot explain itself'
from (
    select count(*) as n
    from {{ ref('srv_drive') }}
    where drives_min_season is null or drives_max_season is null
) probe
where probe.n > 0

union all

select 'no completed in-scope game has any drives'
from (
    select count(*) as n
    from {{ ref('fct_game') }} g
    where g.is_completed
      and g.season >= (select min(season) from {{ ref('fct_drive') }})
      and exists (select 1 from {{ ref('fct_drive') }} d where d.game_id = g.game_id)
) probe
where probe.n = 0
