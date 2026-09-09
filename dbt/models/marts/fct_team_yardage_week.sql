{{ config(materialized='table') }}

-- Yardage LEADING INTO each week. One row per (season, season_type, week, team). R-476.
--
-- Specified by Marc, 2026-09-09, after he caught the defect in the spec that produced it:
-- "it has to divide the yards earned up leading into that game, divided by the number games
-- played prior to that game. Can't find ourselves at Week 10 and looking back to the matchups
-- for a team in Week 2 and have their data for Week 2 showing like they've played through
-- Week 10."
--
-- WHY IT HAS TO EXIST. Serving holds SEASON grain (srv_team_overview) and GAME grain
-- (srv_team_game_log) and nothing in between. A scatter or a matchup panel scoped to Week 2
-- and fed from the season row shows a full season of yardage beside a September game — the
-- composition failure AC-G.33 exists to prevent, and exactly what fct_team_record_week was
-- built for on the wins-and-losses side.
--
-- THE OFF-BY-ONE IS THE ENTIRE POINT OF THE MODEL, and this is fct_team_record_week's rule
-- applied to yards rather than a new idea. The row for week N is cumulative over completed
-- games in weeks strictly BEFORE N. The window frames below end at `1 preceding`, not
-- `current row`, and that single word is the difference between a correct column and one that
-- looks right on every row except the ones anyone checks.
--
-- WALK THE CALENDAR, NOT THE GAMES. dim_team_week is the shared spine — every week in the
-- season crossed with every team in it — and results are LEFT joined on. A team does not play
-- every week; building from its games gives no row for a bye, and a week-filtered page then
-- renders empty instead of carrying the total forward. The spine is REUSED rather than
-- rebuilt: a second spine that drifts from the first is this project's signature defect.
--
-- ORDER BY SEASON TYPE, THEN WEEK — never week alone. Postseason week numbers restart at 1,
-- so ordering on week would sort a bowl game into the middle of October.
--
-- ⚠️ YARDS ALLOWED IS THE OPPONENT'S ROW OF THE SAME GAME, BY SELF-JOIN, AND THAT IS A
-- DECISION RATHER THAN THE ONLY OPTION. fct_game_team carries points_for AND points_against,
-- so an opponent-side column is the established shape there — but it carries NO yardage
-- equivalent, and adding `total_yards_against` to fct_game_team would change a model session
-- B reads through srv_game_team mid-flight. The self-join is local to this model and costs
-- one pass; the column is the better long-term home and is noted for whoever owns that model
-- next.
--
-- ⚠️ THE DENOMINATOR TRAVELS WITH THE NUMERATOR (AC-G.33), AND IT IS NOT "GAMES PLAYED".
-- Yardage comes from box scores and a completed game can lack one — fct_game_team carries
-- has_box_score precisely because that happens. So the count carried here is the number of
-- games THE SUMS WERE ACTUALLY COMPUTED OVER, not the number of games played. Dividing a
-- yardage sum by a games-played count that includes a box-score-less game understates every
-- average by exactly the games we hold nothing for, silently.
--
-- NOTHING IS PRE-DIVIDED HERE. Sums and the count ship; the view or the page divides. A
-- stored average cannot be re-aggregated and hides its own denominator.
with spine as (

    select * from {{ ref('dim_team_week') }}

),

-- One row per team per completed game, carrying both sides of the yardage. The self-join is
-- on the SAME game: o.team_id = g.opponent_team_id is what makes `allowed` the opponent's
-- production rather than a second copy of our own.
team_games as (

    select
        g.season,
        g.season_type,
        g.week,
        g.team_id,
        g.total_yards          as total_yards_for,
        g.rushing_yards        as rushing_yards_for,
        g.passing_yards        as passing_yards_for,
        o.total_yards          as total_yards_allowed,
        o.rushing_yards        as rushing_yards_allowed,
        o.passing_yards        as passing_yards_allowed,
        -- The game counts toward the denominator only if BOTH sides of it are held. A game
        -- where we have our own box score and not the opponent's would otherwise inflate the
        -- "for" average and deflate the "allowed" one from the same row.
        case
            when g.total_yards is not null and o.total_yards is not null then 1
            else 0
        end                    as counted
    from {{ ref('fct_game_team') }} g
    left join {{ ref('fct_game_team') }} o
        on  o.game_id = g.game_id
        and o.team_id = g.opponent_team_id
    where g.is_completed
      and g.team_id is not null
      and g.opponent_team_id is not null

),

per_week as (

    select
        season, season_type, week, team_id,
        sum(case when counted = 1 then total_yards_for end)       as week_total_for,
        sum(case when counted = 1 then rushing_yards_for end)     as week_rushing_for,
        sum(case when counted = 1 then passing_yards_for end)     as week_passing_for,
        sum(case when counted = 1 then total_yards_allowed end)   as week_total_allowed,
        sum(case when counted = 1 then rushing_yards_allowed end) as week_rushing_allowed,
        sum(case when counted = 1 then passing_yards_allowed end) as week_passing_allowed,
        sum(counted)                                              as week_games
    from team_games
    group by season, season_type, week, team_id

),

joined as (

    select
        s.season, s.season_type, s.week, s.team_id, s.season_type_ordinal,
        coalesce(w.week_total_for, 0)       as week_total_for,
        coalesce(w.week_rushing_for, 0)     as week_rushing_for,
        coalesce(w.week_passing_for, 0)     as week_passing_for,
        coalesce(w.week_total_allowed, 0)   as week_total_allowed,
        coalesce(w.week_rushing_allowed, 0) as week_rushing_allowed,
        coalesce(w.week_passing_allowed, 0) as week_passing_allowed,
        coalesce(w.week_games, 0)           as week_games
    from spine s
    left join per_week w
        on  w.season      = s.season
        and w.season_type = s.season_type
        and w.week        = s.week
        and w.team_id     = s.team_id

),

running as (

    select
        j.*,
        -- `1 preceding`, NOT `current row`. See the header: this is the off-by-one the model
        -- exists to get right, and assert_team_yardage_week_excludes_its_own_week is the
        -- test that fails the moment this word changes.
        {% set frame = "over (partition by season, team_id order by season_type_ordinal, week"
                       " rows between unbounded preceding and 1 preceding)" %}
        sum(week_total_for)       {{ frame }} as total_yards_for,
        sum(week_rushing_for)     {{ frame }} as rushing_yards_for,
        sum(week_passing_for)     {{ frame }} as passing_yards_for,
        sum(week_total_allowed)   {{ frame }} as total_yards_allowed,
        sum(week_rushing_allowed) {{ frame }} as rushing_yards_allowed,
        sum(week_passing_allowed) {{ frame }} as passing_yards_allowed,
        sum(week_games)           {{ frame }} as games_counted
    from joined j

)

select
    {{ surrogate_key(['season', 'season_type', 'week', 'team_id']) }} as team_yardage_week_sk,
    season,
    season_type,
    season_type_ordinal,
    week,
    team_id,
    -- NULL, NOT ZERO, WHERE NOTHING HAS BEEN COUNTED YET. At week 1 a team has played no
    -- games, and 0 total yards is a measurement it did not make — the same null-not-zero rule
    -- that makes total_points null rather than zero on an unplayed game. `games_counted` is
    -- the column that says which case a null is, and it is 0 rather than null so a consumer
    -- can filter on it without a coalesce.
    coalesce(games_counted, 0) as games_counted,
    case when coalesce(games_counted, 0) > 0 then coalesce(total_yards_for, 0) end
        as total_yards_for,
    case when coalesce(games_counted, 0) > 0 then coalesce(rushing_yards_for, 0) end
        as rushing_yards_for,
    case when coalesce(games_counted, 0) > 0 then coalesce(passing_yards_for, 0) end
        as passing_yards_for,
    case when coalesce(games_counted, 0) > 0 then coalesce(total_yards_allowed, 0) end
        as total_yards_allowed,
    case when coalesce(games_counted, 0) > 0 then coalesce(rushing_yards_allowed, 0) end
        as rushing_yards_allowed,
    case when coalesce(games_counted, 0) > 0 then coalesce(passing_yards_allowed, 0) end
        as passing_yards_allowed
from running
