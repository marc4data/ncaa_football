-- 🚨 A283 (cfdb-main-R-4801): RE-POINTED FROM `mart_team_season_record` TO `srv_standings`.
--
-- The mart was the legacy contract and the site stopped reading it on 2026-08-20; the strangler's
-- last step never ran. `srv_standings` mirrors its column names and semantics (`_models.yml:1196`).
--
-- ⚠️ THIS RE-POINT DOES NOT REMOVE THE RACE AND MUST NOT BE READ AS IF IT DID. `srv_standings` is
-- outside the two-hourly selector while every one of its 22 ancestors is inside it, so a long
-- weekly build still snapshots the two sides at different moments. That is cfdb-main-R-4803 and it
-- is a scheduling question, not a test one.
-- Reconciliation (data quality rule #4): a team's W-L-T must account for every
-- game it played. Returns offending rows; dbt fails the test if any come back.

select
    team_season_key,
    games_played,
    wins + losses + ties as accounted_for
from {{ ref('srv_standings') }}
where wins + losses + ties != games_played
