{{ config(materialized='table') }}

-- A COACH'S SEASON AT ONE SCHOOL, WITH THE TENURE IT BELONGS TO. R-766.
-- One row per (coach_id, team_id, season).
--
-- Marc, 2026-09-14: "We need a Coach Card, not sure where it fits yet" — and, asked what "color"
-- meant, "Color = We need to add some structure and information about the coach involved in the
-- game." ✅ THIS ROUND IS THE STRUCTURE HALF. The card's content is a later round he judges from
-- a render, which is what "not sure where it fits yet" asks for.
--
-- 🚨 `/coaches` HAS BEEN FETCHED SINCE THE FIRST BACKFILL AND NOTHING DOWNSTREAM READ IT.
-- `stg_coach_season` (12,564 rows) and `stg_coach_season_detail` (451) both existed; no mart and
-- no serving model touched either, and `srv_team_overview`'s header lists coach among the things
-- that are NOT there. Third time in three days: R-723's post-game leaders and R-724's
-- win-probability curve were the same shape — the data was there, the page could not reach it.
--
-- ── 🚨 A GAME CANNOT BE ATTRIBUTED TO A COACH, AND THAT IS MEASURED RATHER THAN ASSUMED ───────
--
-- The gate for this round asked how many (season, team) pairs carry more than one coach:
--
--     all time      199 of 12,361 pairs    1.61%
--     2024-2026      43 of    408 pairs   10.54%   <- the seasons a reader actually looks at
--
-- ⚠️ TEN PERCENT IS NOT "~ZERO", so the simple design the gate hoped for is not available. East
-- Carolina 2024 is the clearest case: Mike Houston 7 games (3-4), Blake Harrell 6 games (5-1),
-- across a 13-game season. NOTHING IN THE FEED SAYS WHICH SIX.
--
-- ✅ SO THIS MODEL NAMES THE SEASON'S COACHES AND REFUSES TO GUESS WHICH GAMES ARE WHOSE.
-- `coaches_in_team_season` travels on every row so a page can say "2024 head coach" where the
-- season had one and something honest where it had two. A card naming the wrong coach for a game
-- is worse than one that says "2026 head coach".
--
-- ✅ AND CFBD FLAGS ITS OWN UNCERTAINTY, WHICH IS WORTH CARRYING RATHER THAN RE-DERIVING.
-- `stg_coach_season_detail.attribution_complete` is FALSE on exactly 32 rows, and ALL 32 are in
-- multi-coach seasons — East Carolina 2024's two rows among them, with null home/away splits
-- beside them. That is the vendor saying "we could not split this season", in their column.
--
-- ⚠️ THE DETAIL TABLE IS NOT REDUNDANT AND IT IS NOT A SUBSET TO IGNORE: 66 columns against 19,
-- covering 2024-2026 over 138 teams. It is the MODERN-ERA table — conference, postseason, home,
-- away and neutral splits, poll weeks, CFP, recruiting and draft. This model takes only
-- `attribution_complete` from it; the rest is a later round's material and is left where it is.
--
-- ── 🚨 THE TENURE COMES FROM CONSECUTIVE SEASONS, NEVER FROM `hired_at` ───────────────────────
--
-- `stg_coach_season.hired_at` belongs to the COACH and repeats on every season row — Steve
-- Addazio carries 2012-12-04 on all seven of his Boston College seasons — so it is the date of
-- his most recent hire, not the hire that began a given tenure. It is also NULL for older rows
-- (Alex Agase, Northwestern 1964).
--
-- ⚠️ A COACH WHO LEFT AND RETURNED IS TWO TENURES, AND A GAP YEAR IS THE BOUNDARY. Measured:
--
--     Barry Alvarez   Wisconsin   1990-2005 (16y), 2012 (1y), 2014 (1y)   <- three tenures
--     Bob Neyland     Tennessee   1926-1934, 1936-1940, 1946-1952         <- war service
--     Chris Ault      Nevada      1992, 1994-1995, 2004-2012
--
-- A `hired_at` boundary would give each of them ONE tenure beginning at their latest hire, and a
-- card reading "in his 4th season" when it is his 12th is the kind of error a reader spots and we
-- do not. `assert_coach_tenures_split_on_a_gap_year` is what makes that checkable.
--
-- ⚠️ THE COACH'S RECORD IS CFBD'S OWN PER-COACH FIGURE, NOT DERIVED FROM `fct_game`, AND THE GATE
-- IS WHY. `fct_game` knows team results and nothing about coaches; splitting a 13-game season
-- into 7 and 6 would mean attributing games, which the measurement above says cannot be done.
-- Using the vendor's split and carrying their `attribution_complete` beside it is the honest
-- shape. ✅ `assert_coach_season_record_reconciles_with_the_team` checks the single-coach case,
-- where the two sources MUST agree.
with seasons as (

    select
        c.coach_id,
        c.first_name,
        c.last_name,
        c.team_id,
        c.school,
        c.season,
        c.games,
        c.wins,
        c.losses,
        c.ties,
        c.win_percentage,
        -- 🚨 THE GAP-YEAR TRICK: season minus a dense rank over the coach's seasons at this
        -- school is CONSTANT across consecutive years and changes at every break. It is the
        -- whole tenure definition, and it never reads a date.
        c.season - row_number() over (partition by c.coach_id, c.team_id order by c.season)
            as tenure_group
    from {{ ref('stg_coach_season') }} c

),

tenures as (

    select
        coach_id, team_id, tenure_group,
        min(season)  as tenure_first_season,
        max(season)  as tenure_last_season,
        count(*)     as tenure_seasons
    from seasons
    group by coach_id, team_id, tenure_group

),

-- How many coaches that school had in that season — the honesty flag, computed once.
coaches_per_team_season as (

    select season, team_id, count(*) as coaches_in_team_season
    from {{ ref('stg_coach_season') }}
    group by season, team_id

)

select
    {{ surrogate_key(['s.coach_id', 's.team_id', 's.season']) }}     as coach_team_season_sk,
    s.coach_id,
    s.first_name,
    s.last_name,
    s.first_name || ' ' || s.last_name                              as coach_name,
    s.team_id,
    s.school,
    s.season,

    -- ── THE TENURE ────────────────────────────────────────────────────────────────────────
    -- Which spell at this school this season belongs to: 1 for the first, 2 after a gap.
    dense_rank() over (partition by s.coach_id, s.team_id order by t.tenure_first_season)
                                                                    as tenure_number,
    t.tenure_first_season,
    t.tenure_last_season,
    t.tenure_seasons,
    s.season - t.tenure_first_season + 1                            as season_in_tenure,

    -- ── THIS SEASON ───────────────────────────────────────────────────────────────────────
    s.games,
    s.wins,
    s.losses,
    s.ties,
    s.win_percentage,

    -- ── THE TENURE TO DATE, INCLUDING THIS SEASON ─────────────────────────────────────────
    sum(s.games)  over (partition by s.coach_id, s.team_id, t.tenure_group
                        order by s.season rows between unbounded preceding and current row)
                                                                    as tenure_games_to_date,
    sum(s.wins)   over (partition by s.coach_id, s.team_id, t.tenure_group
                        order by s.season rows between unbounded preceding and current row)
                                                                    as tenure_wins_to_date,
    sum(s.losses) over (partition by s.coach_id, s.team_id, t.tenure_group
                        order by s.season rows between unbounded preceding and current row)
                                                                    as tenure_losses_to_date,

    -- ── THE TENURE BEFORE THIS SEASON ─────────────────────────────────────────────────────
    -- ⚠️ AC-G.32: a coach in his FIRST season of a tenure has no prior record, and that is NULL
    -- rather than 0. Zero wins and no seasons yet are different facts, and a card reading "0-0
    -- coming in" about a first-year coach has invented a record he does not have. The frame ends
    -- at `1 preceding`, so the first row of every tenure is null by construction.
    sum(s.wins)   over (partition by s.coach_id, s.team_id, t.tenure_group
                        order by s.season rows between unbounded preceding and 1 preceding)
                                                                    as tenure_wins_before_season,
    sum(s.losses) over (partition by s.coach_id, s.team_id, t.tenure_group
                        order by s.season rows between unbounded preceding and 1 preceding)
                                                                    as tenure_losses_before_season,

    -- ── THE HONESTY FLAGS ─────────────────────────────────────────────────────────────────
    cts.coaches_in_team_season,
    -- ⚠️ NULL, NOT FALSE, WHERE THE VENDOR PUBLISHES NOTHING. The detail table covers 2024-2026
    -- only, so every earlier row has no opinion — which is a different fact from "CFBD says the
    -- attribution is incomplete". AC-G.11.
    d.attribution_complete
from seasons s
join tenures t
  on  t.coach_id = s.coach_id and t.team_id = s.team_id
  and t.tenure_group = s.tenure_group
join coaches_per_team_season cts
  on cts.season = s.season and cts.team_id = s.team_id
-- LEFT: the detail table is 2024-2026 only, and a row without it is not a row without a coach.
left join {{ ref('stg_coach_season_detail') }} d
  on  d.coach_id = s.coach_id and d.team_id = s.team_id and d.season = s.season
