-- R-351. EVERY DRIVE IN staging.stg_drive MUST REACH marts.fct_drive.
--
-- THE GAP THIS CLOSES, NAMED BY B046 ITSELF. fct_drive joins the game spine with an INNER
-- join (fct_drive.sql: `join fct_game g on g.game_id = d.game_id`), deliberately — a drive
-- whose game is not in the spine has no season, no week and no venue, and carrying it would
-- put a row on the page that cannot say when it happened.
--
-- But an inner join is a silent filter. If fct_game ever lags stg_drive — a slate landing in
-- raw before the game spine is rebuilt, a scope boundary moving, an upstream dedup change —
-- drives disappear from the mart and NOTHING ELSE NOTICES:
--
--   * assert_srv_drive_keeps_every_drive compares fct_drive against srv_drive. Both sides
--     would be short by the same amount, so it passes. B046 flagged that in its own report.
--   * The page renders a game with possessions missing from the middle of its sequence and
--     looks entirely healthy doing so. It does not error; it answers.
--
-- So the assertion has to be made against STAGING, which is the only place that still knows
-- how many drives there were. This is the test the inner join exists to be checked by.
--
-- It fails LOUD rather than warning: a missing possession is not a data-quality nuance, it is
-- a wrong answer to "what happened in this game".
select
    d.drive_id,
    d.game_id,
    d.offense,
    d.drive_number,
    'in stg_drive, absent from fct_drive' as failure
from {{ ref('stg_drive') }} d
left join {{ ref('fct_drive') }} f on f.drive_id = d.drive_id
where f.drive_id is null
