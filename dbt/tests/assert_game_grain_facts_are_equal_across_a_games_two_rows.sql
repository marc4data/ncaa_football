-- A GAME-GRAIN FACT REPEATED ON BOTH ROWS MUST BE THE SAME FACT ON BOTH ROWS.
--
-- R-266 added venue, attendance, excitement and the upset flag to a game x TEAM view. That
-- direction is the allowed one — the grain rule forbids pushing FINER grain into a coarser
-- view, not the reverse — but it is only safe while the two rows agree. If they ever disagree
-- the view is quietly claiming a game had two attendances, and every aggregate over it is
-- wrong in a way that looks like real variance rather than a defect.
--
-- The realistic way this breaks is a fan-out: a join that returns two rows for one game_id
-- would produce exactly this, and would ALSO change the row count — which is why this checks
-- the values rather than the count. A duplicate that happened to carry identical values is
-- caught by the grain's own uniqueness test; a join picking up the wrong row is caught here.
--
-- `as_of_ts` is included for a different reason: it is read as a scalar subquery precisely so
-- that a second mart_as_of row raises instead of doubling the view. This is the belt to that
-- brace.
--
-- Zero violations across 110,879 games on 2026-09-05.
select
    game_id,
    count(distinct venue_display)    as venues,
    count(distinct attendance)       as attendances,
    count(distinct excitement_index) as excitements,
    count(distinct is_upset)         as upset_flags,
    count(distinct as_of_ts)         as as_of_stamps
from {{ ref('srv_game_team') }}
group by game_id
having count(distinct venue_display)    > 1
    or count(distinct attendance)       > 1
    or count(distinct excitement_index) > 1
    or count(distinct is_upset)         > 1
    or count(distinct as_of_ts)         > 1
