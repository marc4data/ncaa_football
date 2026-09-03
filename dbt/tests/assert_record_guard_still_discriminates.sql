-- The other half of R-127: widening the guard must not have widened it to EVERYONE.
--
-- Marc's rule, stated as the thing that must never happen: a team whose results we do not
-- hold must not be shown a record. Concretely — a non-FBS side in the spine only because it
-- appears on somebody else's schedule, which has already taken the field this season and has
-- no completed game in the warehouse, is a team whose true record is not 0-0.
--
-- THE FIRST VERSION OF THIS TEST ASSERTED ON THE POPULATION, not the rule: it failed unless
-- some row somewhere was unknown. That passes on production (6,125 of 485,005 rows, 1.3%) and
-- fails on any dataset that happens to contain no stubs — which is exactly what CI has. A
-- test that depends on the data having a particular shape is testing the fixture.
select r.season, r.season_type, r.week, r.team_id, r.current_record
from {{ ref('fct_team_record_week') }} r
join {{ ref('dim_team') }} t
  on t.team_id = r.team_id and t.season = r.season
where not t.is_fbs
  and not r.has_completed_games      -- no results held for this team, all season
  and r.record_is_known              -- ...and yet we are claiming to know its record
