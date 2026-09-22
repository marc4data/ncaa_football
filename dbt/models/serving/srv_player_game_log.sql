-- Players page: game log, one row per player x game x category x stat type.
--
-- 2024+ only, because box scores are `recent` scope. A player with a 2015 season on the
-- season tab and nothing here is the honest state, not a defect — srv_player_stats runs
-- back to 2004 and this cannot.
--
-- Narrower than the fact on purpose; see srv_player_stats for why serving columns are
-- rationed rather than copied.
--
-- 🚨 A146, cfdb-main-R-1000. EIGHT COLUMNS ARRIVED, AND "RATIONED RATHER THAN COPIED" IS WHY THEY
-- HAD TO BE ASKED FOR RATHER THAN ASSUMED PRESENT. Marc, Today v01: *"Player Yardage, Touchdowns,
-- Defensive Leaders: include [Jersey #, Name, Year (left aligned)], Position (right aligned within
-- the Player cell)"* and *"Teams, include logo and Rank"*.
--
-- A144 measured the block and stopped: this view carried none of the three player attributes, and
-- its team side had `team` and no slug, logo, rank or record. ⚠️ **A page may not join** — *"display
-- only: single-table SELECT + WHERE"* — so a leaderboard could not reach them and the cell could
-- not be built. Three rounds reported it; this is the one that moves them.
--
-- ── 🚨 THE GRAIN QUESTION, MEASURED RATHER THAN WAVED AT ─────────────────────────────────────
--
-- `dim_athlete` is SEASON x PLAYER and this view is GAME x PLAYER, so joining it asserts the
-- attribute did not change during the season. **That is a claim, and it was checked:**
--
--     of 68,347 season-players, how many carry more than one jersey?    0
--                                                  more than one position?   0
--                                                  more than one class year? 0
--
-- ✅ So the attributes are stable within a season and the assertion the join makes is true.
--
-- 🚨 BUT THE DIMENSION IS NOT UNIQUE ON (season, player_id) — 68,357 rows against 68,347 distinct
-- pairs — AND THE NAIVE JOIN WOULD HAVE FANNED OUT. The ten duplicates are MID-SEASON TRANSFERS:
-- two team rows, same jersey, same position (`assert_dim_athlete_duplicate_slugs_are_only_transfers`
-- is the guard that says so).
--
-- ✅ **SO THE JOIN IS ON `athlete_sk`, WHICH THE FACT ALREADY CARRIES AND WHICH IS UNIQUE — 68,357
-- rows, 68,357 distinct, zero duplicates.** It cannot fan out, and it picks the row for the team
-- the player was on FOR THAT GAME rather than an arbitrary one of two. **The safe key was already
-- on the table; the obvious key was the wrong one.**
--
-- ⚠️ THE NULL RATES ARE MEASURED PER COLUMN, AND THEY ARE HIGHER THAN THE DIMENSION'S OWN GAP.
-- `has_athlete_dimension` is false on 8.61% of rows — but a dimension row can EXIST and carry a
-- null attribute, so the three do not share that figure and it would have been wrong to quote it
-- for them. Of 1,410,331 rows:
--
--     position             152,907   10.8%
--     class_year_display   152,959   10.8%
--     jersey               161,159   11.4%
--     team_rank          1,222,044   86.6%   <- expected: the poll is a Top 25, so NULL is
--                                               UNRANKED, a published fact rather than a gap
--     team_logo_url          9,339    0.66%
--     team_display / team_slug / record_before_display   4,283   0.30%
--
-- ✅ EVERY ONE IS AN HONEST ABSENCE A PAGE MUST RENDER AS ONE (AC-G.11), which is why these are
-- LEFT joins: an inner join would have silently dropped 11% of the leaderboard's own rows.
--
-- 🚨 AND THE COST IS REAL AND IS STATED RATHER THAN ASSUMED. On disk this view went 324 MB -> 451
-- MB, **+127 MB**, and it is in HEAVY_SERVING — the WEEKLY publish, which A139 measured at 1,004
-- MB, so this is +12.6% of it. ⚠️ `team_logo_url` IS 72.5 MB OF THE 120.6 MB OF COLUMN DATA — a
-- per-team URL repeated 1.41M times, 60% of the cost for one of eight columns. **It is carried
-- because the page may not join and the cell needs a logo**, and because the publish transfers a
-- COMPRESSED dump (A137) where a column with ~700 distinct values across 1.41M rows costs very
-- little of the wire. If the weekly publish ever needs the space back, this column is where it is.
--
-- ⚠️ `record_before_display` CARRIES ITS MOMENT IN ITS NAME, and the name is the guard —
-- `srv_game_team.sql` says so in those words. It is `fct_team_record_week.current_record` for this
-- game's week, which is built on a `1 preceding` frame, so it is the record the team took INTO the
-- fixture. ❌ There is no after-record here: this view has no completed/scheduled split to choose
-- with, and A144's `table.record_span` shows the before-record and titles every row with which
-- moment it describes.
select
    g.player_game_stat_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.game_date,
    g.start_date,
    g.player_id,
    g.player_slug,
    g.player_name,
    g.team,
    g.team_id,
    g.conference,
    g.home_away,
    g.opponent,
    g.opponent_team_id,
    g.team_points,
    g.stat_category,
    g.stat_type,
    g.stat_raw,
    g.stat_value,
    g.stat_made,
    g.stat_attempted,
    -- 🚨 THE RATE IS COMPUTED HERE BECAUSE §4.2 SAYS THE PAGE MAY NOT. R-611.
    --
    -- `players.py:_value` rendered `f"{int(made)}/{int(attempted)} ({made / attempted * 100:.0f}%)"`
    -- — arithmetic BETWEEN TWO COLUMNS, done in the app. Cowork's ruling, which B accepted without
    -- re-litigating: scaling ONE column by a constant for display is rendering; dividing one
    -- column by another is a metric, and metrics live upstream.
    --
    -- ⚠️ CARRIED AS A FRACTION RATHER THAN A PERCENTAGE, so the page's remaining `* 100` is the
    -- permitted kind of arithmetic — one column, one constant, for display. It also matches every
    -- other share in this warehouse (`usage_total` of 0.042 is 4.2%), so nobody has to remember
    -- which of two conventions a given column follows.
    --
    -- ⚠️ NULL WHEN `stat_attempted` IS 0 OR ABSENT, never zero. A player who attempted nothing has
    -- no rate; reporting 0% would be a measurement he did not earn — the same rule that makes
    -- total_points null rather than zero for an unplayed game.
    case when g.stat_attempted is not null and g.stat_attempted <> 0
         then cast(g.stat_made as {{ dbt.type_float() }}) / g.stat_attempted
    end                                                        as stat_made_rate,

    -- ── THE PLAYER CELL (A146) ──────────────────────────────────────────────────────────────
    -- Marc's `[Jersey #, Name, Year]` left, `Position` right. `player_name` is already above.
    ath.jersey,
    ath.position,
    ath.class_year_display,

    -- ── THE TEAM CELL (A146) ────────────────────────────────────────────────────────────────
    -- The four facts `table.team_cell` and `table.record_span` read, spelled as `srv_game_team`
    -- spells them so one page-side producer serves both relations without a second adapter.
    dt.team_slug,
    dt.team_display,
    -- 🚨 A191 (cfdb-main-R-2005). THE SHORT NAME, BECAUSE THE FULL ONE DOES NOT FIT ON A CARD.
    --
    -- > **MARC, 2026-09-21:** *"team name under the logo, readable. If the full name can't fit
    -- > at the card width, use the site's existing short/abbreviated team name."*
    --
    -- 📊 MEASURED IN CHROMIUM ON THE REAL PAGE, 2026 week 3: the card's team track is 57.6px
    -- and **15 of 40 names overflow it** — "South Dakota State" draws 94.4px, "Mississippi
    -- Valley State" 112.9px. ⚠️ **AND THE WIDTH CANNOT BE BOUGHT FROM THE CARD**: at a 1100px
    -- viewport the player-name track beside it is already down to 90.9px with 56 of 150 rows
    -- overflowing, so widening the team column makes a worse defect than it fixes.
    --
    -- ✅ `abbreviation` IS THE SITE'S EXISTING SHORT NAME, NOT A NEW ONE — `srv_teams_index`,
    -- `srv_team_overview` and `srv_standings` publish it under that name, `srv_game` as
    -- `home_abbreviation`/`away_abbreviation` and `srv_game_team` as `opponent_abbreviation`.
    -- It is at most 9 characters. **The page could not reach it (G-2 — one relation per query)
    -- and `dim_team` has been in this join since A146**, so this is one line, exactly as the
    -- colour was two rounds ago.
    --
    -- ⚠️ IT IS NULL FOR SOME TEAMS (Chicago State among this week's), so the page falls back to
    -- `team_display` rather than drawing an empty cell — an absence must not read as a blank.
    dt.abbreviation                                            as team_abbreviation,
    dt.logo_source_url                                         as team_logo_url,
    -- ── THE TEAM COLOUR (A177, cfdb-main-R-1767) ───────────────────────────────────────────
    -- 🚨 SIX ROUNDS REFUSED THIS AND NONE OF THEM WAS WRONG. A166 asked for the player card's
    -- team name in the team's colour, the page could not join to get it (G-2), and every round
    -- since reported it as a published gap. **The model change is two lines off a join that
    -- was already here for the logo** — `dim_team` has been in this query since A146.
    --
    -- ⚠️ THE NAMES ARE `srv_team_week`'s, DELIBERATELY. That relation publishes exactly this
    -- pair at 0.00% null, and `identity.accent_color` reads `color_on_light`/`color_on_dark`
    -- off a row by those names with an optional prefix. A third spelling for the same fact is
    -- the drift §4.3 exists to prevent, so this is the second publisher of one vocabulary
    -- rather than a new one.
    --
    -- ⚠️ ON-LIGHT / ON-DARK, NOT THE RAW BRAND COLOUR (R-855). Nearly a fifth of teams publish
    -- #000000 as their on-light value; the contrast-safe pair is what a page can actually draw
    -- against either ground, and the browser picks between them through `light-dark()`.
    dt.color_on_light,
    dt.color_on_dark,
    -- ⚠️ THE RANK IS THE GAME'S, NOT THE SEASON'S, and it comes from the same place
    -- `srv_game_team.team_rank` does — `fct_game`'s two rank columns, picked by side. A season
    -- rank would be a different fact wearing this name.
    case when g.home_away = 'home' then fg.home_rank else fg.away_rank end
                                                               as team_rank,
    rw.current_record                                          as record_before_display,
    ao.as_of_ts
from {{ ref('fct_player_game_stat') }} g
-- 🚨 ON `athlete_sk`, NOT ON (season, player_id) — see the header. The obvious key fans out on ten
-- mid-season transfers; this one is unique by construction and picks the right team's row.
left join {{ ref('dim_athlete') }} ath
    on ath.athlete_sk = g.athlete_sk
left join {{ ref('dim_team') }} dt
    on dt.season = g.season and dt.team_id = g.team_id
left join {{ ref('fct_game') }} fg
    on fg.game_id = g.game_id
left join {{ ref('fct_team_record_week') }} rw
    on  rw.season = g.season and rw.season_type = g.season_type
    and rw.week = g.week and rw.team_id = g.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'player_game') ao
