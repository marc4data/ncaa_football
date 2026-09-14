{{ config(materialized='table') }}

-- The coach a page can put on a card. R-766. One row per (coach_id, team_id, season).
--
-- ⚠️ THE ARITHMETIC IS NOT HERE. `fct_coach_team_season` owns the tenure boundary, the running
-- records and every decision about what can and cannot be attributed; this view attaches the
-- provenance stamp and does nothing else.
--
-- 🚨 WHAT A PAGE MAY AND MAY NOT SAY WITH THIS, because the distinction is the whole round:
--
--   ✅ "Ohio State's 2026 head coach"        — always true, one row per (team, season, coach)
--   ✅ "in his 20th season at Air Force"     — `season_in_tenure`, derived from CONSECUTIVE
--                                              seasons, never from `hired_at`
--   🚨 "the coach in THIS GAME"              — NOT AVAILABLE, and not because the model is thin.
--                                              10.54% of 2024-2026 (season, team) pairs had more
--                                              than one coach, and nothing in the feed says which
--                                              games are whose. `coaches_in_team_season` is how a
--                                              page knows to soften the sentence.
select
    c.coach_team_season_sk,
    c.coach_id,
    c.coach_name,
    c.first_name,
    c.last_name,
    c.team_id,
    c.school,
    c.season,
    c.tenure_number,
    c.tenure_first_season,
    c.tenure_last_season,
    c.tenure_seasons,
    c.season_in_tenure,
    c.games,
    c.wins,
    c.losses,
    c.ties,
    c.win_percentage,
    c.tenure_games_to_date,
    c.tenure_wins_to_date,
    c.tenure_losses_to_date,
    c.tenure_wins_before_season,
    c.tenure_losses_before_season,
    c.coaches_in_team_season,
    c.attribution_complete,
    ao.as_of_ts
from {{ ref('fct_coach_team_season') }} c
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
