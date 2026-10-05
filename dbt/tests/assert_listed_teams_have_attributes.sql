-- 🚨 A283 (cfdb-main-R-4801): RE-POINTED FROM `mart_team_season_record` TO `srv_standings`.
--
-- The mart was the legacy contract and the site stopped reading it on 2026-08-20; the strangler's
-- last step never ran. `srv_standings` mirrors its column names and semantics (`_models.yml:1196`).
--
-- ⚠️ THIS RE-POINT DOES NOT REMOVE THE RACE AND MUST NOT BE READ AS IF IT DID. `srv_standings` is
-- outside the two-hourly selector while every one of its 22 ancestors is inside it, so a long
-- weekly build still snapshots the two sides at different moments. That is cfdb-main-R-4803 and it
-- is a scheduling question, not a test one.
-- Integrity of the season-scoped team join: if a team-season matched the season's team
-- list, it must carry that season's attributes. A row flagged as listed but missing a
-- school or classification means the join matched on the wrong grain.

select
    team_season_key,
    school,
    classification
from {{ ref('srv_standings') }}
where is_listed_team
  and (school is null or classification is null)
