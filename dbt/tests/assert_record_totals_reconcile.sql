-- Reconciliation (data quality rule #4): a team's W-L-T must account for every
-- game it played. Returns offending rows; dbt fails the test if any come back.

select
    team_season_key,
    games_played,
    wins + losses + ties as accounted_for
from {{ ref('mart_team_season_record') }}
where wins + losses + ties != games_played
