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

    ao.as_of_ts
from {{ ref('fct_team_yardage_week') }} y
join {{ ref('dim_team') }} d
    on  d.season  = y.season
    and d.team_id = y.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
