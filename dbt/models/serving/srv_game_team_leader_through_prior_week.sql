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
-- 🚨 THE THREE KPI SLOTS ARE CARRIED AS DATA, LABEL INCLUDED — A116, R-717. Marc asked for "3
-- stats KPI w/name of the measure above the metric", and the panel already decides WHICH stats
-- apply, so the panel decides what they are CALLED. B091's precedent in as many words: "that
-- pairing is Marc's and it is carried as DATA, not prose — the page reads the column rather than
-- choosing."
--
-- ⚠️ THE ALTERNATIVE WAS A panel -> labels MAP IN THE PAGE, and it was rejected for the reason
-- `ci/check_publish_build_agreement.py` exists one layer down: a second list, in a second
-- language, that can silently disagree with the columns it describes. A page that hardcodes
-- "Receptions" for slot 1 of the passing panel is correct until the day the trio changes, and then
-- it is confidently wrong. Here, changing a trio is one `case` branch and the page does not move.
--
-- ⚠️ AND THE PAGE STILL DOES NOT COMPUTE (§4.2). It reads a label, a number and a format name.
-- `stat_n_format` names the RENDERING rather than the arithmetic — the volatile half (which stats,
-- what they are called) is data, the stable half (how an integer differs from a one-decimal
-- average) is three branches of display code that do not change when the trio does.
--
--     format       slots that use it                     the page renders
--     integer      receptions, yards, touchdowns         1,284
--     decimal_1    yards per carry                       4.8
--     pair         completions / attempts                22-31   (secondary is the denominator)
--
-- 🚨 EVERY SLOT'S VALUE IS `_through_prior_week`, WHICH IS WHY THERE IS NO CURRENT-WEEK COLUMN HERE
-- TO PICK BY MISTAKE. A102's whole lesson: the window belongs in the name, and a page cannot
-- choose the wrong window from a view that only carries one.
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
    l.receptions_through_prior_week,
    l.carries_through_prior_week,
    l.touchdowns_through_prior_week,
    l.completions_through_prior_week,
    l.attempts_through_prior_week,
    l.yards_per_carry_through_prior_week,
    -- 🚨 THE TWELVE SLOT COLUMNS COME FROM A SHARED MACRO — A120, R-723. They used to be written
    -- out here, and A120 added a POST-GAME twin that needs the identical twelve. A second copy is
    -- the drift this project has paid for four times in two weeks, so the expressions moved to
    -- `macros/player_card_slots.sql` and BOTH views call it.
    --
    -- ⚠️ §3.3 EXPAND WITH NO MIGRATE: the column NAMES and VALUES are unchanged and only the
    -- expression's home moved. Proved rather than asserted — A120 checksummed all 75,283 rows of
    -- this view before and after and the md5 was identical.
    {{ player_card_slots(
        panel           = 'l.panel',
        receptions      = 'l.receptions_through_prior_week',
        carries         = 'l.carries_through_prior_week',
        completions     = 'l.completions_through_prior_week',
        attempts        = 'l.attempts_through_prior_week',
        yards           = 'l.yards_through_prior_week',
        touchdowns      = 'l.touchdowns_through_prior_week',
        yards_per_carry = 'l.yards_per_carry_through_prior_week') }},
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
