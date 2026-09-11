-- Matchup page, Travel and rest: one row per (game, team), so a matchup query returns two.
--
-- This section was listed as blocked on "the venue join key" for months. The key was on
-- /games/weather all along — venueId on every row, matching dim_venue 6,847 of 6,847 — which
-- is why this view exists at all and why it is scoped the way it is.
--
-- TWO MEASURES, TWO DIFFERENT COVERAGES, AND A PAGE MUST NOT AVERAGE OVER THE DIFFERENCE.
-- rest_days comes from the schedule and is present for every game that is not a season
-- opener. travel_miles needs coordinates for both the game venue and the team's home venue, so
-- it is 2024+ and 79% even there. NULL means unknown; 0 means they played at home.
--
-- ── R-634: MILES AND FEET ARE THE READER'S UNITS, AND THEY ARE NEW HERE ────────────────────
--
-- 🚨 THIS IS A HANDOVER TO SESSION B AND THE COLUMN NAMES ARE THE HANDOVER. Marc, 2026-09-11:
-- "all distance measurements in miles, elevation measurements in feet." B085 raised it and
-- correctly refused to convert in Streamlit — a unit conversion is a multiplication and it
-- belongs in dbt. So A097 shipped the columns and did NOT touch site/views/matchup.py, which
-- is session B's file (§3 rule 3.1: the change ships the column; the call site is B's to
-- consume on its own round).
--
--     travel_km            →  travel_miles           1 decimal
--     elevation_change_m   →  elevation_change_ft    whole feet, signed
--     game_elevation_m     →  game_elevation_ft      whole feet, absolute
--     home_elevation_m     →  home_elevation_ft      whole feet, absolute
--
-- ⚠️ THE METRIC COLUMNS ARE STILL HERE ON PURPOSE. matchup.py reads travel_km and
-- elevation_change_m today; removing them in the same round that adds their replacements would
-- break a live page belonging to the other session. Once B reads the imperial pair, dropping
-- the metric one is a one-line follow-up — and it should happen, because two units of one
-- measurement side by side is exactly the column pair that invites a reader to compare them.
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
    t.travel_miles,
    t.elevation_change_m,
    t.elevation_change_ft,
    t.game_elevation_m,
    t.game_elevation_ft,
    t.home_elevation_m,
    t.home_elevation_ft,
    t.previous_game_date,
    t.rest_days,
    t.rest_bucket,
    ao.as_of_ts
from {{ ref('fct_game_travel') }} t
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
