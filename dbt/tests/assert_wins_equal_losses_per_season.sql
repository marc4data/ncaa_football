-- 🚨 A283 (cfdb-main-R-4801): RE-POINTED FROM `mart_team_season_record` TO `srv_standings`.
--
-- The mart was the legacy contract and the site stopped reading it on 2026-08-20; the strangler's
-- last step never ran. `srv_standings` mirrors its column names and semantics (`_models.yml:1196`).
--
-- ⚠️ THIS RE-POINT DOES NOT REMOVE THE RACE AND MUST NOT BE READ AS IF IT DID. `srv_standings` is
-- outside the two-hourly selector while every one of its 22 ancestors is inside it, so a long
-- weekly build still snapshots the two sides at different moments. That is cfdb-main-R-4803 and it
-- is a scheduling question, not a test one.
-- Reconciliation (data quality rule #4): every completed game produces exactly one
-- winner and one loser, so league-wide wins must equal losses within a season.
--
-- This catches a whole class of bugs the per-row tests can't: a game counted from
-- only one side, a duplicated matchup, or a bad home/away unpivot.
--
-- Caveat this deliberately tolerates: games against non-FBS/non-D1 opponents that
-- aren't in the teams list still appear here, which is correct — the check is on
-- games, not on roster completeness.

select
    season,
    sum(wins)   as total_wins,
    sum(losses) as total_losses
from {{ ref('srv_standings') }}
group by season
having sum(wins) != sum(losses)
