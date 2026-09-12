-- The three players leading this team in a metric GOING INTO this game. R-687.
--
-- ONE ROW PER game x team x panel x leader_rank, top three only.
--
-- 🚨 THIS IS NOT `srv_game_team_leader`, AND THE NAME IS LONG ON PURPOSE. That view answers
-- "who led IN this game", from the game's own box score. This one answers "who leads the team
-- COMING INTO this game", accumulated over earlier weeks and containing NOTHING from the game
-- it is attached to. Two objects, two windows, both honestly called "leaders".
--
-- ⚠️ A102 IS WHY THE WINDOW IS IN THE NAME RATHER THAN ONLY IN A COMMENT. That round spent
-- itself on `spread_move_from_open` and `line_spread_move_from_open` — two near-identically
-- named columns measuring different windows, which two reader-facing surfaces each picked a
-- different one of, and which disagreed on 83% of games. The prefix had done its job in the
-- model and nothing stopped a page choosing wrong. `_through_prior_week` is that lesson applied
-- before the fact rather than after it.
--
-- ⚠️ THE ARITHMETIC IS NOT HERE. fct_player_leader_week owns the accumulation, the leakage
-- frame, the pairing and the ranking; this view only attaches those rows to a game and
-- pre-joins the three display attributes. That split is deliberate and it is also what made
-- the model finish: the first attempt did all of it in one serving view and did not complete in
-- ten minutes, because a CTE referenced more than once is materialised WITHOUT STATISTICS and
-- Postgres estimated `rows=1` against ~400,000 real rows, chose nested loops and went
-- quadratic. A mart is a real table with real statistics. A097 lost an hour to the same class.
--
-- ⚠️ JERSEY, POSITION AND CLASS COME FROM `dim_athlete` AND ARE NULLABLE, deliberately.
-- Measured on 2026: FBS teams resolve 96.7% of their yards to an athlete row, non-FBS 0% — the
-- 2026 roster load covers 138 of 305 teams and was last refreshed 2026-08-15. A leader whose
-- roster row is missing still appears, with the name and the yards the box score always
-- carries, and with null jersey/position/class. Dropping him would silently remove a real team
-- leader in order to protect three display fields.
--
-- ⚠️ `class_year_display` IS READ, NOT REBUILT. dim_athlete already maps 1-4 to FR/SO/JR/SR and
-- already treats anything outside that range as unknown, because "CFBD sometimes sends the
-- season instead". A103 spent a whole round on the cost of a second definition of one string;
-- this is not the round to add another.
select
    {{ surrogate_key(['gs.game_id', 'l.team_id', 'l.panel', 'l.player_id']) }}
        as game_team_leader_through_prior_week_sk,
    gs.game_id,
    l.season,
    l.season_type,
    l.week,
    l.team_id,
    t.team_display,
    t.team_slug,
    gs.opponent_team_id,
    gs.home_away,
    l.panel,
    l.leader_metric,
    l.leader_rank,
    l.tied_players,
    l.qualified_players,
    l.player_id,
    l.player_name,
    l.player_slug,
    l.yards_through_prior_week,
    a.jersey,
    a.position,
    a.class_year_display,
    ao.as_of_ts
from {{ ref('fct_player_leader_week') }} l
-- Both sides of every fixture, so a leader row attaches to the game the reader is looking at.
join (

    select game_id, season, season_type, week, home_team_id as team_id,
           away_team_id as opponent_team_id, 'home' as home_away
    from {{ ref('fct_game') }}
    where season >= 2024 and home_team_id is not null

    union all

    select game_id, season, season_type, week, away_team_id,
           home_team_id, 'away'
    from {{ ref('fct_game') }}
    where season >= 2024 and away_team_id is not null

) gs
  on  gs.season      = l.season
  and gs.season_type = l.season_type
  and gs.week        = l.week
  and gs.team_id     = l.team_id
left join {{ ref('dim_team') }} t
  on  t.season  = l.season
  and t.team_id = l.team_id
left join {{ ref('dim_athlete') }} a
  on a.athlete_sk = l.athlete_sk
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
