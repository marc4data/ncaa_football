-- Each leader's participation share in the games he had played BEFORE this one. R-694.
--
-- ONE ROW PER matchup game x team x panel x player x EARLIER GAME. A row of dots, not a number:
-- the page draws one mark per game the player has already played.
--
-- ⚠️ WHY THIS IS A SEPARATE OBJECT RATHER THAN COLUMNS ON srv_game_team_leader_through_prior_week,
-- which was the alternative Cowork asked to have argued: that view is ONE ROW PER LEADER, and this
-- is one row per leader PER EARLIER GAME. Putting it there would mean either repeating the leader
-- on every game — changing that view's grain and every reader of it — or folding a series into an
-- array, which §4.3's grain rule exists to prevent. The finer grain also serves both renderings: a
-- page wanting a single circle takes the most recent row; a page wanting the series takes them all.
--
-- 🚨 POINT-IN-TIME, AND IT INHERITS A106'S WINDOW RATHER THAN RE-STATING IT. The leader rows come
-- from fct_player_leader_week, whose totals are accumulated with a frame ending at `1 preceding`.
-- The usage rows attached here are the games strictly before the leader row's own week, ordered on
-- (season_type_ordinal, week) — never on week alone, because postseason weeks restart at 1 and a
-- bowl game would otherwise sort into October. Marc's rule: "can only include data through Week 4
-- in a Week 5 game."
--
-- 🚨 THE PAGE MUST NOT DIVIDE (§4.2), SO THE DENOMINATOR IS A COLUMN. Usage is strongly positional
-- — measured medians: QB 0.551, RB 0.134, WR 0.058, TE 0.041 — so a circle filled against a 0-1
-- scale leaves every receiver about 6% full, which is visually indistinguishable from DID NOT PLAY,
-- the one thing the circles exist to show. Cowork's ruling: fill relative to THAT PLAYER'S OWN
-- MAXIMUM in the window — "was this a normal game for him?" — with the absolute share for the
-- hover. Both are carried; the page divides nothing.
--
-- ⚠️ `usage_games_in_window` IS CARRIED FOR THE SINGLE-DATA-POINT PROBLEM, which is B085's shape.
-- A player with ONE earlier game has max = that game = a full circle, which reads as "fully
-- involved" when it means "we have one observation". The page can only say so if it knows the
-- count, so it is a column rather than something the reader is left to infer.
--
-- 🚨 AND THE WHOLE OBJECT IS SILENT ON THE LIVE SEASON. `game/box/advanced` is registered
-- `include=False` — one API call per game, opt-in only — so no DAG fetches it, and every row came
-- from one backfill on 2026-09-01. FBS-vs-FBS completed coverage: 2024 99.2%, 2025 100.0%,
-- **2026 0.0%**. This view is correct and it is EMPTY for every game the site currently shows.
-- Putting that endpoint on a cadence is R-695 and it is a cost decision, not a modelling one:
-- measured, 53 calls to catch 2026 up and roughly 60 a week thereafter.
with game_sides as (

    select game_id, season, season_type, week, home_team_id as team_id
    from {{ ref('fct_game') }}
    where season >= 2024 and home_team_id is not null

    union all

    select game_id, season, season_type, week, away_team_id
    from {{ ref('fct_game') }}
    where season >= 2024 and away_team_id is not null

)

select
    {{ surrogate_key(['gs.game_id', 'w.team_id', 'w.panel', 'w.player_id', 'w.usage_game_id']) }}
        as game_team_leader_usage_sk,
    gs.game_id,
    w.season,
    w.season_type,
    -- Chronological ordering keys. Postseason week numbers restart at 1, so a page sorting these
    -- marks on `week` alone would put a bowl game in the middle of October.
    w.season_type_ordinal,
    w.week,
    w.team_id,
    t.team_display,
    w.panel,
    w.leader_metric,
    w.leader_rank,
    w.player_id,
    w.player_name,
    w.box_position,
    -- The earlier game this mark represents, and where it sits in the sequence.
    w.usage_game_id,
    w.usage_season_type,
    w.usage_season_type_ordinal,
    w.usage_week,
    -- The absolute share, for the hover. 0.042 means 4.2% of the team's plays.
    w.usage_total,
    w.usage_rushing,
    w.usage_passing,
    -- The denominator, so the page divides nothing.
    w.usage_total_max_in_window,
    -- How many observations the maximum is drawn from. 1 means a full circle on one data point.
    w.usage_games_in_window,
    ao.as_of_ts
from {{ ref('fct_player_leader_usage') }} w
join game_sides gs
  on  gs.season      = w.season
  and gs.season_type = w.season_type
  and gs.week        = w.week
  and gs.team_id     = w.team_id
left join {{ ref('dim_team') }} t
  on  t.season  = w.season
  and t.team_id = w.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
