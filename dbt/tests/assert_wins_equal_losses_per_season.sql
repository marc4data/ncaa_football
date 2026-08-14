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
from {{ ref('mart_team_season_record') }}
group by season
having sum(wins) != sum(losses)
