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
-- 🚨 A128 ADDS A FOURTH PANEL, `defensive`, AND IT IS A SEPARATE BRANCH RATHER THAN A WIDENING.
-- `per_player`'s `having sum(yards) is not null` is the OFFENSIVE grain and it is untouched: a
-- tackler records no yards and must never reach that clause. The defensive rows aggregate and
-- qualify on their own terms (`having max(TOT) > 0`) and meet the offensive rows only at the
-- final select, where `panel` and `leader_metric` already distinguish them — which is what the
-- first three panels have always done. The view's declared grain generalises from "a player who
-- recorded yards in this panel" to "a player who recorded THIS PANEL'S OWN MEASURE"; each branch
-- still enforces its own strictly.
--
-- ⚠️ SO `game_yards` IS NULL ON 19.9% OF THIS VIEW'S ROWS, and that is honest rather than
-- missing: a linebacker has no yards. AC-G.32 — null, never 0, because 0 yards would be a
-- measurement of something he never did. The defensive figure lives in `game_tackles`.
--
-- 🚨🚨 TIES ARE THIS PANEL'S CENTRAL PROBLEM AND NO ORDERING SOLVES THEM. MEASURED, 2024-2026,
-- over 4,374 team-games:
--
--     ranked on                      team-games where MORE THAN 3 men occupy ranks 1-3
--     TOT alone                          1,889   43.2%   worst case 12 men
--     TOT, SOLO                            591   13.5%
--     TOT, SOLO, TFL   <- shipped          259    5.9%
--     TOT, SOLO, TFL, SACKS                242    5.5%
--     TOT, SOLO, TFL, SACKS, PD            159    3.6%
--
-- ⚠️ TACKLES ARE SMALL INTEGERS AND SEVEN OF THEM IS A CROWD. The offensive panels have never
-- had to answer this — yards almost never tie.
--
-- 🚨 THE CHAIN IS A CLAIM ABOUT FOOTBALL AND IS STATED AS ONE SO THE NEXT READER CAN DISAGREE
-- WITH THE FOOTBALL RATHER THAN REVERSE-ENGINEER THE SQL:
--
--   1. TOT   — total tackles. The measure. Not a claim.
--   2. SOLO  — "same tackle count, more of them unassisted ranks higher". ⚠️ THE LEAST
--      OPINIONATED TIEBREAK AVAILABLE, because SOLO is a COMPONENT of TOT rather than a
--      different currency — and it does the heavy lifting, 43.2% -> 13.5%.
--   3. TFL   — 🚨 THIS ONE IS A REAL CLAIM: that a tackle for loss is worth more than a tackle.
--      It is applied ONLY to break a tie among equal tackles and equal solos, never to reorder
--      the primary measure.
--
-- ❌ SACKS AND PD ARE DELIBERATELY NOT IN THE CHAIN. Sacks buy 0.4pp and PD 2.3pp, and each adds
-- another claim — PD especially, which would rank a cornerback over a linebacker on a different
-- skill entirely. THE RESIDUAL 5.9% IS LEFT VISIBLE INSTEAD, which is the honest answer:
-- `tied_players` already exists on this view and a defensive card MUST read it. Three named
-- defenders cannot always be ranked fairly, and the model says so rather than inventing a total
-- order the sport does not have.
--
-- ⚠️ AND THE RESIDUAL TIE SHARES A RANK, EXACTLY AS IT DOES ON THE OTHER THREE PANELS. An
-- earlier draft of this branch appended `player_id` to the ordering to make the rank a total
-- order — which produced a tidy three rows per group and 0.0% visible ties. 🚨 THAT WAS A SECOND
-- RULE IN ONE VIEW: the offensive panels return MORE THAN THREE ROWS on a tie deliberately (see
-- above — "the honest shape rather than a silent truncation"), and a page reading this view must
-- not need to know which panel it is looking at to know what a rank means. A silent tiebreak on
-- an arbitrary id is precisely the "page picking one by accident of planner order" this view
-- already refuses.
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

),

-- THE DEFENSIVE PANEL. Its own aggregation, its own qualification, its own ranking measure —
-- see the header. It never passes through `per_player`, so the offensive grain rule is intact.
defensive_per_player as (

    select
        s.game_id, s.season, s.season_type, s.week, s.team_id,
        s.player_id,
        min(s.player_name) as player_name,
        min(s.player_slug) as player_slug,
        min(s.athlete_sk)  as athlete_sk,
        max(s.stat_value) filter (where s.stat_type = 'TOT')   as game_tackles,
        max(s.stat_value) filter (where s.stat_type = 'SOLO')  as game_solo_tackles,
        max(s.stat_value) filter (where s.stat_type = 'TFL')   as game_tackles_for_loss,
        max(s.stat_value) filter (where s.stat_type = 'SACKS') as game_sacks
    from {{ ref('fct_player_game_stat') }} s
    where s.stat_category = 'defensive'
      and s.stat_type in ('TOT', 'SOLO', 'TFL', 'SACKS')
      and s.stat_value is not null
      and s.season >= 2024
    group by s.game_id, s.season, s.season_type, s.week, s.team_id, s.player_id
    -- This branch's own grain: a player who RECORDED A TACKLE in this game. 2,355 of 93,901
    -- defensive box rows carry TOT = 0 — a man who dressed and made no tackle did not lead
    -- anything, exactly as a runner on zero yards does not.
    having max(s.stat_value) filter (where s.stat_type = 'TOT') > 0

),

defensive_ranked as (

    select
        d.*,
        rank() over (
            partition by d.game_id, d.team_id
            order by d.game_tackles desc, d.game_solo_tackles desc,
                     d.game_tackles_for_loss desc) as leader_rank,
        count(*) over (partition by d.game_id, d.team_id) as qualified_players,
        -- ⚠️ TIED ON THE WHOLE CHAIN, not on tackles alone — otherwise the card would say "T-1st"
        -- about two men the ranking has in fact separated on solos.
        count(*) over (partition by d.game_id, d.team_id, d.game_tackles,
                                    d.game_solo_tackles, d.game_tackles_for_loss)
            as tied_players
    from defensive_per_player d

),

-- THE TWO BRANCHES MEET HERE AND NOWHERE EARLIER. Each column a panel does not have is null by
-- construction rather than by omission — see the header on `game_yards`.
combined as (

    select
        game_id, season, season_type, week, team_id,
        player_id, player_name, player_slug, athlete_sk,
        panel,
        leader_rank, tied_players, qualified_players,
        game_yards, game_receptions, game_carries, game_touchdowns,
        game_completions, game_attempts, game_yards_per_carry,
        null::numeric as game_tackles,
        null::numeric as game_solo_tackles,
        null::numeric as game_assisted_tackles,
        null::numeric as game_tackles_for_loss,
        null::numeric as game_sacks
    from ranked

    union all

    select
        game_id, season, season_type, week, team_id,
        player_id, player_name, player_slug, athlete_sk,
        'defensive' as panel,
        leader_rank, tied_players, qualified_players,
        null::numeric, null::numeric, null::numeric, null::numeric,
        null::numeric, null::numeric, null::numeric,
        game_tackles,
        game_solo_tackles,
        -- ASSISTED IS DERIVED, NOT PUBLISHED BY THE FEED: total minus solo. It is the second half
        -- of the Solo-Ast pair and exists so the card can show the tiebreak it is ordered on.
        game_tackles - game_solo_tackles as game_assisted_tackles,
        game_tackles_for_loss,
        game_sacks
    from defensive_ranked

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
        when 'passing'   then 'receiving_yards_in_this_game'
        when 'rushing'   then 'rushing_yards_in_this_game'
        when 'total'     then 'quarterback_total_yards_in_this_game'
        -- ⚠️ THE NAME CARRIES THE WHOLE CHAIN, because the ordering is a claim (see header) and a
        -- reader must be able to see it without opening the SQL.
        when 'defensive' then 'tackles_then_solo_then_tfl_in_this_game'
    end as leader_metric,
    rk.leader_rank,
    rk.tied_players,
    rk.qualified_players,
    rk.player_id,
    rk.player_name,
    rk.player_slug,
    rk.game_yards,
    rk.game_tackles,
    rk.game_solo_tackles,
    rk.game_assisted_tackles,
    rk.game_tackles_for_loss,
    rk.game_sacks,
    {{ player_card_slots(
        panel           = 'rk.panel',
        receptions      = 'rk.game_receptions',
        carries         = 'rk.game_carries',
        completions     = 'rk.game_completions',
        attempts        = 'rk.game_attempts',
        yards           = 'rk.game_yards',
        touchdowns      = 'rk.game_touchdowns',
        yards_per_carry = 'rk.game_yards_per_carry',
        tackles         = 'rk.game_tackles',
        solo            = 'rk.game_solo_tackles',
        assisted        = 'rk.game_assisted_tackles',
        tfl             = 'rk.game_tackles_for_loss') }},
    a.jersey,
    a.position,
    a.class_year_display,
    ao.as_of_ts
from combined rk
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
