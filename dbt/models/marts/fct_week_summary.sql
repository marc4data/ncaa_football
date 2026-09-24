-- ONE ROW PER WEEK: the seven figures Marc's KPI row asks for, each with its denominator.
--
-- > **MARC, v14:** *"Need a KPI summary row - above Most Exciting: # of FBS Games / Avg O/U with
-- > spread / histograms/box-whiskers of Winning Scores vs Losing Scores / % of Favorites that Win
-- > (straight-up) / % of Favorites that Cover (ATS) / % of Over / # of Undefeated Teams that lost"*
--
-- 🚨 WHY THIS IS A MODEL AT ALL. §4.2.1: a page is a single-table SELECT with no joins and no
-- metric arithmetic. Seven rates over a week of games cannot be computed in `today.py`, and a
-- percentage computed in two places is a percentage that will eventually disagree with itself.
--
-- THE GRAIN IS (season, season_type, week) AND DIVISION IS DELIBERATELY NOT IN IT.
--
-- 📊 Looking Back's other sections DO honour the page's Division selector — four query sites in
-- `today.py` carry `(:division = 'all' or is_fbs_game)`. So the question is real, and the answer
-- is still no, for two reasons that agree:
--
--   1. Marc DEFINED this row's population himself: *"every distinct game_id that includes an FBS
--      team"*. That is not "whatever the selector says"; it is a stated rule.
--   2. ⚠️ THE AVERAGE O/U HERE MUST EQUAL THE MEAN OF THE O/U DISTRIBUTION DRAWN UNDER IT, and
--      that distribution comes from `fct_week_metric_distribution`, whose population is already
--      `home_classification = 'fbs' or away_classification = 'fbs'` — the same rule, written into
--      `int_week_metric_value` long before this round. Two populations would let a KPI disagree
--      with its own thumbnail.
--
-- ⚠️ THE CONSEQUENCE IS REAL AND BELONGS TO A216: with the selector on "All", this row stays
-- FBS-scoped while the sections below it widen. **The row has to say so.** It is named in the
-- report rather than solved with a second grain nobody asked for.
--
-- `season_type` IS PART OF THE KEY. Postseason week numbers restart, so (season, week) collides —
-- the record spine learned this first.
--
-- 🚨 EVERY FIGURE BELOW READS THE SAME GAME SET, DEFINED ONCE IN `fbs_games`. A later reader must
-- not widen one of them: if a figure needs a different population it needs a different column, not
-- a different WHERE.
--
-- 🚨 AND EVERY RATE PUBLISHES ITS NUMERATOR, ITS DENOMINATOR AND WHAT WAS EXCLUDED, as columns.
-- A percentage with an unstated denominator is AC-G.11 wearing a number: 60% of five games and
-- 60% of fifty are different facts and the page cannot tell them apart from the rate alone.
{{ config(materialized='table') }}

with games as (
    -- ROW 1'S DEFINITION, AND EVERY OTHER FIGURE READS IT. "Either side is FBS" is Marc's
    -- wording, so an FBS-vs-FCS game counts. `fct_game` is one row per game, so a distinct
    -- count is the row count — asserted by this model's uniqueness test rather than assumed.
    select
        g.game_id, g.season, g.season_type, g.week,
        g.is_completed,
        g.home_points, g.away_points,
        -- THE CLOSING NUMBER IS THE BASIS, per the site's own rule: the favorite is whoever the
        -- market made favorite at close, not at open and not now.
        g.spread_at_close,
        g.total_at_close,
        g.spread_favorite_side,
        g.favorite_covered,
        g.over_met
    from {{ ref('fct_game') }} g
    where g.home_classification = 'fbs' or g.away_classification = 'fbs'
),

scored as (
    select
        *,
        -- A PICK'EM IS NEITHER FAVOURITE NOR DOG. 📊 Measured on 2026 regular: ZERO games close
        -- at exactly 0, and 570 of 888 carry no closing spread at all — which is a different
        -- absence and gets its own column. The branch is written anyway: a rule that has never
        -- fired is still the rule, and the alternative is a pick'em silently joining one side.
        case when spread_at_close = 0 then true else false end       as is_pickem,
        case
            when not is_completed then null
            when spread_at_close is null or spread_at_close = 0 then null
            when spread_favorite_side = 'home'
                then home_points > away_points
            when spread_favorite_side = 'away'
                then away_points > home_points
        end                                                          as favorite_won,
        greatest(home_points, away_points)                           as winning_points,
        least(home_points, away_points)                              as losing_points
    from games
),

by_week as (
    select
        season,
        season_type,
        week,

        -- 1 — FBS GAMES
        count(*)                                                     as fbs_games,
        count(*) filter (where is_completed)                         as fbs_games_completed,

        -- 2 — AVERAGE OVER/UNDER, and what it could not see
        avg(total_at_close)                                          as over_under_mean,
        count(total_at_close)                                        as over_under_games,
        count(*) filter (where total_at_close is null)               as over_under_missing,

        -- 3 — FAVOURITES WINNING STRAIGHT UP
        count(*) filter (where favorite_won)                         as favorite_straight_up_wins,
        count(favorite_won)                                          as favorite_straight_up_games,
        count(*) filter (where is_completed and is_pickem)           as favorite_straight_up_pickems,
        count(*) filter (where is_completed and spread_at_close is null)
                                                                     as favorite_straight_up_no_line,

        -- 4 — FAVOURITES COVERING. 🚨 A PUSH IS NOT A COVER AND NOT A FAIL: it leaves the
        -- denominator entirely and is counted on its own. 📊 One push in 2026 regular so far.
        count(*) filter (where favorite_covered = 'yes')             as favorite_ats_covers,
        count(*) filter (where favorite_covered in ('yes', 'no'))    as favorite_ats_games,
        count(*) filter (where favorite_covered = 'push')            as favorite_ats_pushes,
        count(*) filter (where is_completed and favorite_covered is null)
                                                                     as favorite_ats_no_line,

        -- 5 — OVERS. Same reasoning, same shape. 📊 Two total-pushes in 2026 regular.
        count(*) filter (where over_met = 'yes')                     as overs,
        count(*) filter (where over_met in ('yes', 'no'))            as over_under_decided_games,
        count(*) filter (where over_met = 'push')                    as total_pushes,
        count(*) filter (where is_completed and over_met is null)    as total_no_line,

        -- 7's inputs live in `fct_week_metric_distribution` as distributions; the two scalars
        -- here are the honest summary a KPI tile can show beside them.
        avg(winning_points) filter (where is_completed)              as winning_points_mean,
        avg(losing_points) filter (where is_completed)               as losing_points_mean
    from scored
    group by season, season_type, week
),

undefeated as (
    -- 6 — UNDEFEATED TEAMS THAT LOST, COUNTED AS TEAMS.
    --
    -- ⚠️ TEAMS, NOT GAMES, AND THE DIFFERENCE IS NOT COSMETIC: two undefeated sides meeting
    -- produces exactly one loss and two rows here would double it. The spine is team-grain, so
    -- counting its rows counts teams by construction.
    --
    -- 🚨 "UNDEFEATED ENTERING THE WEEK" COMES FROM THE RECORD SPINE AND IS NOT RE-DERIVED
    -- (decision log 2026-09-02). `fct_team_record_week.wins/losses/ties` are the record LEADING
    -- INTO week N — that is the spine's whole purpose — and `record_is_known` is its own guard
    -- for a team whose earlier fixtures we do not hold.
    --
    -- ⚠️ `wins > 0` IS A DECISION AND IT IS REPORTED AS ONE. A team at 0-0 is undefeated only
    -- vacuously; counting a week-1 loser as "an undefeated team that lost" would make the figure
    -- largest in the week it means least. So a team must have actually won something.
    select
        season, season_type, week,
        count(*) filter (where record_is_known
                           and losses = 0 and ties = 0 and wins > 0
                           and coalesce(losses_after, 0) > 0)        as undefeated_teams_lost,
        count(*) filter (where record_is_known
                           and losses = 0 and ties = 0 and wins > 0) as undefeated_teams_entering
    from {{ ref('fct_team_record_week') }}
    group by season, season_type, week
)

select
    {{ surrogate_key(['b.season', 'b.season_type', 'b.week']) }}     as week_summary_sk,
    b.season,
    b.season_type,
    b.week,

    b.fbs_games,
    b.fbs_games_completed,

    b.over_under_mean,
    b.over_under_games,
    b.over_under_missing,

    b.favorite_straight_up_wins,
    b.favorite_straight_up_games,
    b.favorite_straight_up_pickems,
    b.favorite_straight_up_no_line,

    b.favorite_ats_covers,
    b.favorite_ats_games,
    b.favorite_ats_pushes,
    b.favorite_ats_no_line,

    b.overs,
    b.over_under_decided_games,
    b.total_pushes,
    b.total_no_line,

    b.winning_points_mean,
    b.losing_points_mean,

    coalesce(u.undefeated_teams_lost, 0)                             as undefeated_teams_lost,
    coalesce(u.undefeated_teams_entering, 0)                         as undefeated_teams_entering,

    -- THE RATES, COMPUTED ONCE HERE SO THE PAGE NEVER DOES (§4.2.1).
    -- ⚠️ NULL WHEN THE DENOMINATOR IS ZERO, NOT ZERO. A week nobody has played has no
    -- favorite-win rate; publishing 0.0 would draw a bar at the floor and say something false.
    case when b.favorite_straight_up_games > 0
         then b.favorite_straight_up_wins::numeric / b.favorite_straight_up_games end
                                                                     as favorite_straight_up_rate,
    case when b.favorite_ats_games > 0
         then b.favorite_ats_covers::numeric / b.favorite_ats_games end
                                                                     as favorite_ats_rate,
    case when b.over_under_decided_games > 0
         then b.overs::numeric / b.over_under_decided_games end      as over_rate
from by_week b
-- ⚠️ LEFT JOIN, AND A WEEK WITH NO COMPLETED GAMES STILL PRODUCES A ROW. *No games yet* and *no
-- row for this week* are different facts and the page cannot tell them apart from an empty
-- result (AC-G.11). `by_week` is the spine here because it is built from the fixture list, which
-- exists before anything is played.
left join undefeated u
  on  u.season = b.season and u.season_type = b.season_type and u.week = b.week
