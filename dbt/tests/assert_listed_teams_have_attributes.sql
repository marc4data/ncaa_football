-- Integrity of the season-scoped team join: if a team-season matched the season's team
-- list, it must carry that season's attributes. A row flagged as listed but missing a
-- school or classification means the join matched on the wrong grain.

select
    team_season_key,
    school,
    classification
from {{ ref('mart_team_season_record') }}
where is_listed_team
  and (school is null or classification is null)
