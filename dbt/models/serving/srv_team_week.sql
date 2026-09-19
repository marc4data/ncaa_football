-- Team form LEADING INTO a week. One row per (season, season_type, week, team). R-476.
--
-- ⚠️ WHY A NEW VIEW RATHER THAN COLUMNS ON AN EXISTING ONE — the grain rule decides it, and
-- it was checked rather than assumed. Serving currently holds:
--
--     srv_team_overview   one row per team per SEASON
--     srv_team_rating     one row per team per season per rating SYSTEM
--     srv_team_game_log   one row per (game, team) — GAME grain
--     srv_team_stats      team x season, long
--
-- There is NO team x week object in serving at all. Putting week-grain yardage on
-- srv_team_overview would multiply a season-grain row by ~16 and break every consumer that
-- reads one row per team; putting it on srv_team_game_log would attach a bye-week-carrying
-- figure to a relation that only has rows where a game exists, which is the exact property
-- the calendar spine was built to avoid. So this is a grain nothing covers, and a view named
-- for its grain rather than for the page that asked for it — srv_team_week, not
-- srv_scatter_data.
--
-- ⚠️ IT IS DELIBERATELY GENERAL ENOUGH FOR A MATCHUP LOOKUP, NOT JUST A SCATTER (R-478).
-- Marc's offense-vs-defense pairing is "how Team A produces passing yards compared to how
-- Team B allows passing yards" — two teams, one game, which is Matchup, which is session B's.
-- A lookup by (season, season_type, week, team_id) returns exactly one row, so B reads this
-- twice per game with no aggregation and no window. That is why the key is exposed whole and
-- why rushing and passing are carried separately rather than folded into the total.
--
-- BOTH THE SUMS AND THE PER-GAME FIGURES SHIP. The sums are what re-aggregates; the per-game
-- figures are what a page displays, and they are computed HERE because the app is
-- display-only — a division in Streamlit is metric maths in the app, which is the rule the
-- serving layer exists to keep. The denominator ships beside them so nothing has to guess
-- what it was divided by (AC-G.33).
--
-- ⚠️ games_counted IS NOT "GAMES PLAYED". It is the number of completed games BOTH SIDES of
-- whose box score we hold, which is what the sums were actually computed over. See
-- fct_team_yardage_week's header.
select
    {{ surrogate_key(['y.season', 'y.season_type', 'y.week', 'y.team_id']) }} as team_week_sk,
    y.season,
    y.season_type,
    y.season_type_ordinal,
    y.week,
    y.team_id,
    d.team_slug,
    d.team_display,
    d.logo_source_url        as logo_url,
    d.color_on_light,
    d.color_on_dark,
    d.conference,
    d.classification,
    d.classification = 'fbs' as is_fbs,

    y.games_counted,

    y.total_yards_for,
    y.rushing_yards_for,
    y.passing_yards_for,
    y.total_yards_allowed,
    y.rushing_yards_allowed,
    y.passing_yards_allowed,

    -- Per game, leading into this week. NULL rather than zero where nothing has been counted
    -- yet: at week 1 a team has played nothing, and 0.0 yards per game is a measurement it
    -- did not make. The guard is games_counted > 0 rather than a null check on the numerator,
    -- because a genuine 0-yard game would be a real datum.
    -- ⚠️ R-621. THESE ARE CARRIED, NOT COMPUTED. The division moved into
    -- fct_team_yardage_week when the week-distribution model became a second consumer of the
    -- same metric — see the comment there. Same names, same values, one implementation.
    y.total_yards_for_per_game,
    y.rushing_yards_for_per_game,
    y.passing_yards_for_per_game,
    y.total_yards_allowed_per_game,
    y.rushing_yards_allowed_per_game,
    y.passing_yards_allowed_per_game,

    -- ── WHAT THE SCATTER'S HOVER ASKED FOR (A177, cfdb-main-R-1771) ────────────────────────
    --
    -- > MARC, v09: "Make it hoverable with Logo, Rank, Team, Record, Yards Gained (p##),
    -- > Yards Allowed (p##)"
    --
    -- A176 measured that three of those six were not in this relation and refused to join for
    -- them from the page. Two of the three arrive here; the third is answered rather than
    -- built, below.

    -- RECORD. 📊 A pure join at THIS VIEW'S OWN GRAIN — `fct_team_record_week` is keyed
    -- (season, season_type, week, team_id), which is `fct_team_yardage_week`'s key exactly,
    -- because both were built on `dim_team_week`'s shared spine. Measured coverage against
    -- every row of this view: 2024 100% of rows matched / 99.86% record known, 2025 100% /
    -- 100.00%, 2026 100% / 96.37%.
    --
    -- ⚠️ AND THE SEMANTICS ALREADY AGREE, WHICH IS WHY THIS IS A JOIN AND NOT A COMPUTATION.
    -- This view is form LEADING INTO a week; `current_record` is the record LEADING INTO the
    -- same week — R-285's off-by-one is handled in that model's window frame (`1 preceding`).
    -- A season-grain record joined here would show the final record beside a week 3 row.
    --
    -- ⚠️ SAME SPELLING AS `srv_game_team` AND `srv_player_game_log`. Both publish this fact as
    -- `record_before_display` and `table.record_span` already reads that name, so this is a
    -- third publisher of one vocabulary rather than a third name (§4.3).
    rw.current_record                                        as record_before_display,

    -- RANK. 🚨 THIS ONE IS A DECISION, NOT A JOIN, AND THE DECISION IS NAMED HERE RATHER THAN
    -- BURIED. `fct_poll_rank` is keyed (poll_name, season, season_type, week, team_id) — one
    -- dimension MORE than this view — so attaching "the rank" means CHOOSING a poll.
    -- 📊 Six polls exist for 2025 regular: AP Top 25 (400 rows, 16 weeks), Coaches Poll (400,
    -- 16), FCS Coaches (351, 14), AFCA D-II (326, 13), AFCA D-III (300, 12) and Playoff
    -- Committee (150, 6).
    --
    -- ✅ AP, BECAUSE THE SITE ALREADY DECIDED. `today.py` carries
    -- `POLLS = ("AP Top 25", "Coaches Poll")` and the poll chart defaults to the first. A
    -- relation that disagreed with the page beside it would be a second answer to one
    -- question.
    -- ⚠️ THE NAME SAYS WHICH POLL, so no reader has to come here to find out — `team_rank`
    -- alone is the ambiguity this project has paid for elsewhere (AC-G.33).
    -- ⚠️ NULL IS THE COMMON CASE AND IT IS A FACT: 25 teams of ~136 are ranked in any week, so
    -- unranked is ~82% of FBS rows and every row outside FBS. A page must render that as
    -- "unranked", never as a missing value — which is exactly how `srv_game_team.team_rank`
    -- already behaves (A175 measured it 99% null across all classifications).
    ap.rank                                                  as ap_rank,

    -- PERCENTILE. 🚨 A PERCENTILE WHOSE DENOMINATOR IS UNSTATED IS THE DEFECT AC-G.33 EXISTS
    -- TO PREVENT, and this one has a denominator that CANNOT match what Marc asked for. Said
    -- plainly rather than papered over:
    --
    -- > MARC, v09: "Yards Gained (p##), Yards Allowed (p##)"
    --
    -- A176 read that as *within the drawn population*, and the drawn population is whatever
    -- the page's conference filter and depth leave on screen — it changes as he changes a
    -- control. **A published column is computed once, over a fixed population, and cannot
    -- follow a filter.** The two are different numbers and only one of them can be shipped.
    --
    -- ✅ SO THE FIXED POPULATION IS PUBLISHED AND NAMED: FBS teams with at least one counted
    -- game in the same (season, season_type, week). That is exactly the scatter's own
    -- population WHEN NO CONFERENCE FILTER IS ON, so the common case agrees; under a filter
    -- the number is "of FBS", which is a defensible reading and the one a reader is likelier
    -- to mean. ⚠️ **The page round must render it as "of FBS", not as "of these 14 teams".**
    -- `percentile_population` ships beside them so nothing has to guess the n (AC-G.33, and
    -- `srv_player_stats` sets the precedent with `rank_population`).
    --
    -- ⚠️ HIGHER IS BETTER IN BOTH, WHICH IS WHY THEY ARE NOT THE SAME EXPRESSION. Gained
    -- ascends (more yards is a higher percentile); ALLOWED DESCENDS (fewer yards allowed is a
    -- higher percentile). Encoding that once here is the contract working — a page deciding
    -- which way a percentile reads is metric maths in the app (§4.2.1), and a raw ascending
    -- percentile on "allowed" would put the worst defence in the country at p99.
    case when y.games_counted > 0 and d.classification = 'fbs' then
        round(cast(percent_rank() over (
            partition by y.season, y.season_type, y.week,
                         (y.games_counted > 0 and d.classification = 'fbs')
            order by y.total_yards_for_per_game asc nulls first) as numeric), 4)
    end                                                      as total_yards_for_percentile,
    case when y.games_counted > 0 and d.classification = 'fbs' then
        round(cast(percent_rank() over (
            partition by y.season, y.season_type, y.week,
                         (y.games_counted > 0 and d.classification = 'fbs')
            order by y.total_yards_allowed_per_game desc nulls first) as numeric), 4)
    end                                                  as total_yards_allowed_percentile,
    case when y.games_counted > 0 and d.classification = 'fbs' then
        count(*) over (
            partition by y.season, y.season_type, y.week,
                         (y.games_counted > 0 and d.classification = 'fbs'))
    end                                                      as percentile_population,

    -- ⚠️ THE OPPONENT IS NOT HERE, AND THAT IS A FINDING RATHER THAN AN OMISSION
    -- (cfdb-main-R-1772). Marc asked for one in the hover. **This view's grain cannot answer
    -- it**, and the measurement says so rather than the reasoning:
    --
    --     games that team played that week      team-weeks (2025, whole spine)
    --     0                                      5,652      <- a bye has NO opponent
    --     1                                      7,601
    --     2                                         24      <- and these have no single one
    --     3                                          3
    --     4                                          1
    --
    -- 🚨 AND THE SEMANTIC GAP IS THE LARGER HALF. This view is a team's CUMULATIVE FORM
    -- ENTERING a week — `_profile`'s own docstring says so, and every figure above is over
    -- completed games in EARLIER weeks. The week's opponent is a fact about a GAME, and
    -- `srv_game_team` is the relation at that grain and already carries the whole opponent
    -- block. Adding an opponent here would put a game-grain fact on a row that is explicitly
    -- not about a game, and 42.6% of the spine's rows would carry null for a reason a reader
    -- could not see.
    --
    -- 📋 **So the tooltip line is not built and the question goes back to Marc** (§2.1 — what
    -- the site should say is his): a hover on this panel can name the opponent only if the
    -- panel changes what it is about.

    ao.as_of_ts
from {{ ref('fct_team_yardage_week') }} y
join {{ ref('dim_team') }} d
    on  d.season  = y.season
    and d.team_id = y.team_id
left join {{ ref('fct_team_record_week') }} rw
    on  rw.season      = y.season
    and rw.season_type = y.season_type
    and rw.week        = y.week
    and rw.team_id     = y.team_id
left join {{ ref('fct_poll_rank') }} ap
    on  ap.season      = y.season
    and ap.season_type = y.season_type
    and ap.week        = y.week
    and ap.team_id     = y.team_id
    and ap.poll_name   = 'AP Top 25'
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
