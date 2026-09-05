-- Offense and defense arrive as strings and are resolved to ids through dim_team within
-- season. A null id is the expected non-FBS case — /games is the authority on who played and
-- /teams on who is an FBS programme, and the first set is larger.
--
-- SEVERITY IS WARN because the nulls are correct. The test exists to COUNT them rather than
-- let them pass unseen: rows are kept, never dropped, so the only way an unresolved team shows
-- up is if something looks for it.
--
-- ⚠️ WHAT WOULD BE A REAL DEFECT is an FBS team failing to resolve — that means the name in
-- /drives does not match the name in /teams for that season, and every drive attributed to it
-- is orphaned. The conference is the tell: a team with a listed conference that still has no
-- id is not a Division II visitor.
{{ config(severity='warn') }}

select
    season,
    offense                       as team,
    offense_conference            as conference,
    count(*)                      as drives
from {{ ref('fct_drive') }}
where offense_team_id is null
  and offense_conference is not null
group by season, offense, offense_conference
