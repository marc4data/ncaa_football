{{ config(materialized='table') }}

-- The win-probability curve a chart draws, at serving. R-724.
--
-- ONE ROW PER (game_id, play). `fct_game_win_probability_play` owns the arithmetic, the period
-- join and every decision about what a play carries; this view attaches the calendar a page
-- filters on and the provenance stamp, and does nothing else.
--
-- ⚠️ THAT SPLIT IS NOT DECORATION — `ci/assert_layer_boundaries` REFUSED THE VERSION WITHOUT IT.
-- The first attempt read `stg_game_win_probability` and `stg_play` straight from serving, on the
-- precedent of `srv_game_team_leader` being "a serving-layer window over the mart, with no new
-- mart". The precedent did not apply: that view HAD a mart at its grain, and at play grain there
-- was none, because `fct_game_win_probability_summary` collapses the curve to one row per game.
-- The mart's header carries the full reasoning.
--
-- 🚨 COWORK'S NOTE SAID "that would be the largest object in serving" AND IT IS FALSE — measured
-- across all 32 serving models BEFORE building: this ranks SIXTH of thirty-three at 291,548 rows,
-- against srv_player_stats at 1,521,532 and srv_player_play at 375,925. ✅ So it is built whole and
-- nothing is downsampled: a thinned curve is a DIFFERENT CHART and a reader cannot tell, because
-- the peaks a reader is drawn to are exactly the points a sampler drops.
--
-- 📊 COVERAGE, bounded by the settled play-by-play scope decision rather than by this model:
--
--     season   plays    games   no period   overtime plays   overtime games
--     2024    139,052     912           0             381               34
--     2025    124,486     803           0             345               33
--     2026     28,010     183           1              61                3
--     total   291,548   1,898           1             787               70
--
-- 🚨 A 2019 GAME HAS NO CURVE, AND THAT IS A SCOPE DECISION RATHER THAN MISSING DATA. AC-G.11: the
-- page must say WHICH absence it is — "outside the play-by-play window" reads differently from
-- "this game has no win probability", and a 2024+ game with no rows here is the second.
--
-- 🚨 THE LEAKAGE RULE DOES NOT APPLY TO THIS VIEW, AND A LATER ROUND MUST NOT "FIX" IT.
-- `fct_player_leader_week` is point-in-time by construction — `rows between unbounded preceding
-- and 1 preceding` — because a preview card is read BEFORE kickoff. This object is the other side
-- of that line: it describes a COMPLETED game and is read afterwards, to say what happened.
-- Scoping it to prior weeks would make every row describe a different game. (A120 wrote this same
-- sentence for the post-game leader twin; the two read as one rule on purpose.)
select
    c.game_win_probability_play_sk,
    c.game_id,
    g.season,
    g.season_type,
    g.week,
    c.play_id,
    c.play_number,
    c.period,
    c.is_overtime,
    c.home_win_probability,
    c.home_team_id,
    c.home_team,
    c.away_team_id,
    c.away_team,
    c.home_score,
    c.away_score,
    c.down,
    c.distance,
    c.yard_line,
    c.home_has_ball,
    c.play_text,
    ao.as_of_ts
from {{ ref('fct_game_win_probability_play') }} c
-- INNER, deliberately: a curve for a game the warehouse does not model has no page to appear on,
-- and `season` / `season_type` / `week` come from here.
join {{ ref('fct_game') }} g
  on g.game_id = c.game_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'play') ao
