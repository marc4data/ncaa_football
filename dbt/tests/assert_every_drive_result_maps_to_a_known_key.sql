-- drive_result is CFBD free text and it selects an ICON. An unmapped value must FAIL rather
-- than render a blank glyph.
--
-- THE PRECEDENT IS THE PROVIDER MAPPING (2026-08-17): the line feed turned out to carry both
-- "DraftKings" and "Draft Kings", two spellings that would have silently split a comparison.
-- Free text from an upstream feed grows new values without warning, and the only defence is a
-- test that fails on the new one.
--
-- The measured vocabulary is 25 values over 78,502 drives. This fires on the 26th.
select
    drive_result,
    count(*) as drives
from {{ ref('fct_drive') }}
where drive_result is not null
  and drive_result_key is null
group by drive_result
