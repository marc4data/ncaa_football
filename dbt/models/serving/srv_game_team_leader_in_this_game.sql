{{ config(materialized='table') }}

-- The three players who led this team IN THIS GAME, in the three panels Matchup uses. R-723.
--
-- ONE ROW PER game x team x panel x leader_rank, top three only — the same grain as
-- `srv_game_team_leader_through_prior_week`, which is the point: it is the SAME CARD on the
-- OTHER WINDOW.
--
-- 🚨 THIS IS THE POST-GAME TWIN AND THE WINDOW IS THE ONLY REAL DIFFERENCE — SAY IT IN THESE
-- WORDS, BECAUSE THE TWO NAMES DIFFER BY ONE SUFFIX AND A102 SPENT A WHOLE ROUND ON A PAIR THIS
-- SIMILAR:
--
--     srv_game_team_leader_through_prior_week   who leads the team GOING INTO this game,
--                                               accumulated over EARLIER weeks and containing
--                                               NOTHING from the game it is attached to
--     srv_game_team_leader_in_this_game (here)  who led IN this game, from this game's own
--                                               box score and nothing else
--
-- 🚨 THE LEAKAGE RULE DOES NOT APPLY TO THIS VIEW, AND A LATER ROUND MUST NOT "FIX" IT.
-- `fct_player_leader_week` is point-in-time by construction — `rows between unbounded preceding
-- and 1 preceding` — because Marc's rule is "Can only include data through Week 4 in a Week 5
-- game", and a preview card is read BEFORE kickoff. This object is the other side of that line:
-- it describes a COMPLETED game and is read afterwards, to say what happened. Scoping it to
-- prior weeks would make every column describe a different game.
--
-- ⚠️ A SERVING-LAYER WINDOW OVER THE MART, WITH NO NEW MART — `srv_game_team_leader`'s own
-- precedent, itself following `srv_player_stats` over `fct_player_season_stat`. There is no
-- accumulation to store and no second reader: the ranking is one pass over this game's rows.
-- The preview needed a mart because its window spans weeks and cost ten minutes as a CTE; this
-- one does not.
--
-- ⚠️ MARC'S PAIRING IS DELIBERATE AND `panel` CARRIES IT. "Passing will be top 3 receivers.
-- Rushing is top 3 yards rushing, Total is the Top 3 QBs." The PASSING panel is accompanied by
-- the people who CAUGHT the passes. `fct_player_yardage_week`'s header owns that reasoning; this
-- view applies the same pairing to a single game and does not re-decide it.
--
-- 🚨 MEASURED BEFORE BUILDING, BECAUSE R-534 REJECTED A PER-PLAYER GRAIN TWICE AND ITS NUMBERS
-- ARE IN `srv_game_team_leader`'s header. The reason those numbers do not apply here is SCOPE,
-- and scope is the whole argument:
--
--     R-534, per-player across all 50 (stat_category, stat_type) pairs, top 3 both ends
--                                                          1,201,737 rows   90% of the fact
--     R-534, same but top 1 both ends                        959,247 rows   72%
--     what shipped — one row per group                       296,629 rows   22%
--     THIS VIEW — 3 panels, HIGH end only, top 3              54,071 rows    3.8%
--
-- 5.6% of the smallest option R-534 rejected. The per-player grain is affordable here precisely
-- because the card asks for three panels rather than fifty stats, and for leaders rather than
-- both extremes.
--
-- ⚠️ TIES SHARE A RANK — `rank()`, not `row_number()`, as in the preview. Two backs on 96 yards
-- are jointly second, and a page picking one by accident of planner order shows a different name
-- on each load. A three-way tie for third therefore returns more than three rows, which is the
-- honest shape rather than a silent truncation, and `tied_players` is how a page knows to write
-- "T-2nd".
--
-- 🚨 AC-G.11 FOR WHOEVER DRAWS THESE: A GROUP OFTEN CANNOT FILL THREE CARDS, and on one panel
-- that is the normal case rather than the edge. Measured over 2024-2026:
--
--     panel     groups   with fewer than 3 leaders
--     passing    7,341        50   (0.7%)
--     rushing    7,343       481   (6.6%)
--     total      6,736     6,300  (93.5%)   <- a team plays ONE quarterback
--
-- ✅ AND THAT MATCHES MARC'S OWN WORDING. v03 reads "Include QA, Top 3 Rusher" — QB SINGULAR,
-- three rushers. The v02 pairing "Total -> top 3 QBs" was about the PREVIEW, where a team may
-- have used three quarterbacks across a season; in ONE GAME it almost never has.
--
-- ⚠️ JERSEY, POSITION AND CLASS COME FROM `dim_athlete` AND ARE NULLABLE, deliberately, exactly
-- as on the preview view: the 2026 roster load covers 138 of 305 teams, so a leader whose roster
-- row is missing still appears with the name and the yards the box score always carries.
-- Dropping him would silently remove a real leader to protect three display fields.
with contributions as (

    -- ⚠️ ONE ROW PER BOX-SCORE STAT ROW, pivoted into the measures, exactly as
    -- fct_player_yardage_week does it. The grouping below sums them to the player grain, which
    -- matters for the total panel where passing and rushing both contribute.
    select s.game_id, s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'passing' as panel,
           case when s.stat_type = 'YDS' then s.stat_value end as yards,
           case when s.stat_type = 'REC' then s.stat_value end as receptions,
           null::numeric                                       as carries,
           case when s.stat_type = 'TD'  then s.stat_value end as touchdowns,
           null::numeric                                       as completions,
           null::numeric                                       as attempts
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'receiving'
      and s.stat_type in ('YDS', 'REC', 'TD')
      and s.stat_value is not null
      and s.season >= 2024

    union all

    select s.game_id, s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'rushing',
           case when s.stat_type = 'YDS' then s.stat_value end,
           null::numeric,
           case when s.stat_type = 'CAR' then s.stat_value end,
           case when s.stat_type = 'TD'  then s.stat_value end,
           null::numeric,
           null::numeric
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'rushing'
      and s.stat_type in ('YDS', 'CAR', 'TD')
      and s.stat_value is not null
      and s.season >= 2024

    union all

    -- TOTAL YARDS FOR A QUARTERBACK IS PASSING PLUS RUSHING, and the touchdowns are both too —
    -- the panel ranks total offence, so a passing-only touchdown count beside it would describe
    -- the same quarterback two ways in one card row. A116's judgement, unchanged here.
    --
    -- 🚨 `C/ATT` CARRIES NO `stat_value` — it is a PAIR, and `stat_made` / `stat_attempted` are
    -- the parsed halves. Hence the exception in the filter: without it every quarterback silently
    -- loses his first slot.
    select s.game_id, s.season, s.season_type, s.week, s.team_id,
           s.player_id, s.player_name, s.player_slug, s.athlete_sk,
           'total',
           case when s.stat_type = 'YDS'   then s.stat_value end,
           null::numeric,
           null::numeric,
           case when s.stat_type = 'TD'    then s.stat_value end,
           case when s.stat_type = 'C/ATT' then s.stat_made end,
           case when s.stat_type = 'C/ATT' then s.stat_attempted end
    from {{ ref('fct_player_game_stat') }} s
    join {{ ref('dim_athlete') }} a
      on  a.athlete_sk = s.athlete_sk
      and a.position = 'QB'
    where s.stat_category in ('passing', 'rushing')
      and s.stat_type in ('YDS', 'TD', 'C/ATT')
      and (s.stat_value is not null or s.stat_type = 'C/ATT')
      and s.season >= 2024

),

per_player as (

    select
        game_id, season, season_type, week, team_id, player_id, panel,
        min(player_name) as player_name,
        min(player_slug) as player_slug,
        min(athlete_sk)  as athlete_sk,
        sum(yards)       as game_yards,
        sum(receptions)  as game_receptions,
        sum(carries)     as game_carries,
        sum(touchdowns)  as game_touchdowns,
        sum(completions) as game_completions,
        sum(attempts)    as game_attempts
    from contributions
    group by game_id, season, season_type, week, team_id, player_id, panel
    -- The grain this view declares: a player who recorded yards in this game, in this panel.
    having sum(yards) is not null

),

ranked as (

    -- The `where` runs BEFORE the window, which in Postgres it does: a player on zero yards did
    -- not lead anything and must not occupy a rank.
    select
        p.*,
        rank()  over (partition by p.game_id, p.team_id, p.panel order by p.game_yards desc)
            as leader_rank,
        count(*) over (partition by p.game_id, p.team_id, p.panel)
            as qualified_players,
        count(*) over (partition by p.game_id, p.team_id, p.panel, p.game_yards)
            as tied_players,
        -- Yards per carry, divided HERE and not in the page (§4.2), over this game's totals.
        -- ⚠️ NULL WHEN THERE ARE NO CARRIES, never zero — AC-G.32, and A116's own rule for the
        -- preview twin. A card printing 0.0 for a receiver who never ran has invented a
        -- measurement rather than omitted one.
        case when p.game_carries > 0
             then round(p.game_yards / p.game_carries, 1)
        end as game_yards_per_carry
    from per_player p
    where p.game_yards > 0

)

select
    {{ surrogate_key(['rk.game_id', 'rk.team_id', 'rk.panel', 'rk.player_id']) }}
        as game_team_leader_in_this_game_sk,
    rk.game_id,
    rk.season,
    rk.season_type,
    rk.week,
    rk.team_id,
    t.team_display,
    t.team_slug,
    gs.opponent_team_id,
    gs.home_away,
    rk.panel,
    -- The pairing, restated as data on every row, so a page or a test can assert the crossing
    -- without reading prose. ⚠️ The names say IN THIS GAME, because the preview view's identical
    -- column says `receiving_yards` for a season-to-date figure and these must not be confused.
    case rk.panel
        when 'passing' then 'receiving_yards_in_this_game'
        when 'rushing' then 'rushing_yards_in_this_game'
        when 'total'   then 'quarterback_total_yards_in_this_game'
    end as leader_metric,
    rk.leader_rank,
    rk.tied_players,
    rk.qualified_players,
    rk.player_id,
    rk.player_name,
    rk.player_slug,
    rk.game_yards,
    {{ player_card_slots(
        panel           = 'rk.panel',
        receptions      = 'rk.game_receptions',
        carries         = 'rk.game_carries',
        completions     = 'rk.game_completions',
        attempts        = 'rk.game_attempts',
        yards           = 'rk.game_yards',
        touchdowns      = 'rk.game_touchdowns',
        yards_per_carry = 'rk.game_yards_per_carry') }},
    a.jersey,
    a.position,
    a.class_year_display,
    ao.as_of_ts
from ranked rk
-- Both sides of every fixture, so a leader row knows who it was playing and which side it was on.
join (

    select game_id, home_team_id as team_id, away_team_id as opponent_team_id, 'home' as home_away
    from {{ ref('fct_game') }}
    where season >= 2024 and home_team_id is not null

    union all

    select game_id, away_team_id, home_team_id, 'away'
    from {{ ref('fct_game') }}
    where season >= 2024 and away_team_id is not null

) gs
  on  gs.game_id = rk.game_id
  and gs.team_id = rk.team_id
left join {{ ref('dim_team') }} t
  on  t.season  = rk.season
  and t.team_id = rk.team_id
left join {{ ref('dim_athlete') }} a
  on a.athlete_sk = rk.athlete_sk
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
where rk.leader_rank <= 3
