-- R-127. A TEAM THAT HAS NOT PLAYED YET HAS A KNOWN RECORD, AND IT IS 0-0.
--
-- The guard used to be `season_games > 0`, a window over the WHOLE season partition, so it
-- asked a question about the future. Eight games into 2026 it was true only for the teams that
-- had ALREADY played — so the Schedule card showed "0-0" beside Arkansas-Pine Bluff, which
-- opened on 29 August, and NOTHING beside Missouri, Oklahoma and UTEP, which had not opened
-- yet. Precisely backwards, and invisible mid-season because by then every team qualifies.
--
-- Scoped to FBS because that is the whole of Marc's rule: 0-0 is the truth for a team that has
-- not played, and a lie for a Division II side in the spine only because it appears on
-- somebody else's schedule. `assert_record_guard_still_discriminates` holds the other side.
select r.season, r.team_id, r.record_is_known, r.current_record
from {{ ref('fct_team_record_week') }} r
join {{ ref('dim_team') }} t
  on t.team_id = r.team_id and t.season = r.season
where t.is_fbs
  and r.season_type = 'regular'
  and r.week = 1
  and r.current_record is null
