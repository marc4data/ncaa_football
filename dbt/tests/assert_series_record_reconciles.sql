-- A head-to-head record must account for every meeting it counts.
--
-- srv_game derived the away side of the series as `series_games - series_home_team_wins`,
-- which is correct only in a sport without draws. College football has 2,600 tied games on
-- record and had no overtime before 1996, so every one of those was silently credited to the
-- away team — overstating it in 40,045 of 102,985 rows.
--
-- Nothing could have caught that by inspection. A head-to-head record is the figure a reader
-- is least able to check: nobody arrives already knowing that Yale leads Princeton 70-45-10,
-- so 70-55 would have read as authoritative for as long as it stood.
--
-- The invariant that does catch it is arithmetic rather than semantic: wins plus losses plus
-- ties equals meetings. That also caught the second defect in the same pass — two games
-- flagged completed with no score recorded were counted as meetings while producing no
-- outcome, giving a record of 0-0-0 over one game.
select
    game_id,
    series_games,
    series_home_team_wins,
    series_away_team_wins,
    series_ties
from {{ ref('srv_game') }}
where series_games is not null
  and series_home_team_wins + series_away_team_wins + series_ties <> series_games
