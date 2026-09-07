-- "start time (of game)" is ambiguous between the game clock at the snap and elapsed from
-- kickoff, so fct_drive carries BOTH and Marc picks against a real render. This asserts both
-- are actually there, because a column that is null in practice resolves nothing.
--
-- REGULATION ONLY, and that boundary is deliberate. College overtime has no game clock, so
-- elapsed-from-kickoff is undefined there and is null by design rather than by omission —
-- 326 drives at period >= 5, plus 24 at period 0, which is a source defect and not a period.
-- drive_number orders those rows, which is why it is the y-axis and these two are labels.
select
    drive_id,
    game_id,
    drive_number,
    start_period,
    start_clock_display,
    elapsed_from_kickoff_seconds
from {{ ref('fct_drive') }}
where start_period between 1 and 4
  and (start_clock_display is null or elapsed_from_kickoff_seconds is null)
