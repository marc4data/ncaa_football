{{ config(materialized='table') }}

-- Per-game participation share, by player. R-694.
--
-- One row per (game_id, team_id, player_id). `usage_total` of 0.042 means the player was on the
-- field for 4.2% of his team's plays — A SHARE, not a rate, and not a count.
--
-- ⚠️ THE GRAIN IS THE GAME, NOT THE WEEK, AND THE FIRST BUILD GOT THAT WRONG. Keyed on
-- (season, season_type, week, team_id, player_id) it produced 34,549 rows against 34,268 distinct
-- keys — 202 keys duplicated, every one of them a team playing TWICE in the same week. Measured,
-- not guessed: `dim_team` is unique on (season, school), so no join was fanning out; the grain
-- declaration was simply false.
--
-- 🚨 AND THE FIX IS NOT TO SUM THE WEEK. `usage_total` is a SHARE of one game's plays. Two games at
-- 0.50 is not a week at 1.00, and averaging them is a different metric that nobody has asked for.
-- Per game is the only shape this number is honest at, which is why the model is named for it.
--
-- 🚨 THE SOURCE MODEL HAD NO READER AT ALL. `stg_game_box_player` has carried usage and PPA since
-- the box-score family shipped and NOTHING referenced it — zero `ref()`s, verified. Marc found it.
-- Cowork had previously ruled that per-game participation did not exist, having checked
-- `stg_player_season_usage` (season grain) and `srv_player_play` and not this one.
--
-- ⚠️ AND THE REASON IT HAS NO READER IS WORTH CARRYING HERE, because it bounds what this model can
-- honestly be used for: `game/box/advanced` is registered `include=False` under the heading
-- "Per-game fan-out: opt-in only" — one API call per game — so NO DAG FETCHES IT. Every row in it
-- came from a single backfill on 2026-09-01 between 03:50 and 05:57 UTC. Measured coverage of
-- FBS-vs-FBS completed games: 2024 99.2%, 2025 100.0%, **2026 0.0%**. Until that endpoint is put on
-- a cadence, this model is a complete record of two finished seasons and silent on the live one.
--
-- 🚨 NO ATHLETE ID ON THE PAYLOAD — THE KEY IS A NAME, AND THE SOURCE MODEL SAYS SO ITSELF:
-- "Two players with the same name in one game would collide, and there is nothing in the response
-- that could separate them." So the name is resolved to a real `player_id` through
-- `fct_player_game_stat`, which carries both.
--
-- ⚠️ AND THE COLLISION IS NOT THEORETICAL. Measured: 4 of 185,427 (game, team, name) keys in
-- `fct_player_game_stat` map to TWO DIFFERENT athletes — including Michigan's two Will Johnsons in
-- 2024. **An ambiguous name resolves to NEITHER player, never to the first one.** Attaching one
-- player's usage to another is invisible on a page and wrong in a way a reader would believe.
-- `ambiguous` below is an anti-join, not a `distinct on`.
--
-- ⚠️ THE QUARTER AND RUSHING/PASSING SPLITS COME ALONG BECAUSE THEY ARE FREE — same row, same join,
-- no extra scan. THE PPA FAMILY DOES NOT. PPA is points per play, a RATE; the source model's own
-- header warns "both are small decimals and neither is the other". It answers a different question,
-- has no proposed reader, and a column with no reader is the R-492 class. It stays one `ref()` away
-- for the round that wants it.
--
-- ⚠️ `season_type_ordinal` IS CARRIED RATHER THAN LOOKED UP LATER. Postseason week numbers restart
-- at 1, so anything ordering these rows needs it — and A106's leakage test had to join
-- `dim_team_week` to get it, which is what made that test straddle a refresh boundary and earn a
-- `full_refresh_only` tag. Carrying it here keeps this model's consumers out of that trap.
-- ⚠️ THIS MODEL TAKES ~158 SECONDS TO BUILD AND THE REASON IS STRUCTURAL, NOT INCIDENTAL.
-- `stg_game_box_player` is a VIEW over raw JSON, so every reference to it re-explodes 1,860 raw
-- documents. EXPLAIN shows it inlined as a Subquery Scan beneath the join. Two consequences,
-- both measured:
--
--   1. REFERENCE IT ONCE. An "optimisation" that also read it to pre-filter the games needing name
--      resolution DOUBLED the JSON work and pushed the build past ten minutes.
--   2. `count(distinct player_id)` forces a GroupAggregate with a sort of fct_player_game_stat's
--      1.34M rows, and `work_mem` here is 4MB, so that sort spills. Any variation that widens the
--      sort key makes it dramatically worse — A107 abandoned a staged break after four attempts
--      for exactly this reason (see the report).
--
-- 158 seconds for a table rebuilt weekly at most is an acceptable price; knowing WHY is what stops
-- the next round from "optimising" it into something slower.

with resolved_names as (

    -- One row per (game, team, name) that maps to EXACTLY ONE athlete.
    select game_id, team_id, player_name, min(player_id) as player_id
    from {{ ref('fct_player_game_stat') }}
    group by game_id, team_id, player_name
    having count(distinct player_id) = 1

),

usage as (

    select
        b.game_id,
        b.team,
        b.player_name,
        b.position,
        b.usage_total,
        b.usage_quarter1,
        b.usage_quarter2,
        b.usage_quarter3,
        b.usage_quarter4,
        b.usage_rushing,
        b.usage_passing
    from {{ ref('stg_game_box_player') }} b
    where b.usage_total is not null

)

select
    {{ surrogate_key(['u.game_id', 't.team_id', 'r.player_id']) }}
        as player_usage_game_sk,
    g.season,
    g.season_type,
    w.season_type_ordinal,
    g.week,
    u.game_id,
    t.team_id,
    r.player_id,
    u.player_name,
    -- The position the ADVANCED BOX SCORE lists, which is not necessarily dim_athlete's. Carried
    -- because usage is strongly positional — measured medians: QB 0.551, RB 0.134, WR 0.058,
    -- TE 0.041 — so any reader comparing two players needs to know it is comparing like with like.
    u.position as box_position,
    u.usage_total,
    u.usage_quarter1,
    u.usage_quarter2,
    u.usage_quarter3,
    u.usage_quarter4,
    u.usage_rushing,
    u.usage_passing
from usage u
join {{ ref('fct_game') }} g
  on g.game_id = u.game_id
-- The payload names the team; dim_team.school is the same vocabulary.
join {{ ref('dim_team') }} t
  on  t.season = g.season
  and t.school = u.team
-- 🚨 AN INNER JOIN ON PURPOSE. A name that resolves to two athletes is absent from
-- `resolved_names`, so it drops out here rather than being attached to the wrong player.
join resolved_names r
  on  r.game_id = u.game_id
  and r.team_id = t.team_id
  and r.player_name = u.player_name
join {{ ref('dim_team_week') }} w
  on  w.season      = g.season
  and w.season_type = g.season_type
  and w.week        = g.week
  and w.team_id     = t.team_id
