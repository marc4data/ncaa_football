-- Matchup page, Travel and rest: one row per (game, team), so a matchup query returns two.
--
-- This section was listed as blocked on "the venue join key" for months. The key was on
-- /games/weather all along — venueId on every row, matching dim_venue 6,847 of 6,847 — which
-- is why this view exists at all and why it is scoped the way it is.
--
-- TWO MEASURES, TWO DIFFERENT COVERAGES, AND A PAGE MUST NOT AVERAGE OVER THE DIFFERENCE.
-- rest_days comes from the schedule and is present for every game that is not a season
-- opener. travel_km needs coordinates for both the game venue and the team's home venue, so
-- it is 2024+ and 79% even there. NULL means unknown; 0 means they played at home.
select
    t.game_travel_sk,
    t.game_id,
    t.team_id,
    t.team,
    t.opponent_team_id,
    t.opponent,
    t.season,
    t.week,
    t.season_type,
    t.game_date,
    t.is_home,
    t.is_neutral_site,
    t.game_venue,
    t.travel_km,
    t.elevation_change_m,
    t.game_elevation_m,
    t.home_elevation_m,
    t.previous_game_date,
    t.rest_days,
    t.rest_bucket,
    ao.as_of_ts
from {{ ref('fct_game_travel') }} t
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
