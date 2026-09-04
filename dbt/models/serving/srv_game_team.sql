-- THE game x team serving surface: one row per team per game. R-077.
--
-- NOTHING SAT AT THIS GRAIN BEFORE. That is why 150 measure columns across four staging
-- models — box-score advanced, team advanced, havoc and PPA — had no downstream consumer and
-- were invisible from the inside: landed, staged, and never once selected.
--
-- THE GRAIN RULE IS WHY THEY ARE HERE AND NOT ON srv_game (Marc, ratified 2026-09-02):
-- "Can't add game.team grain to a table that is at game grain." srv_game carries game-grain
-- columns and DERIVED both-team summaries; a per-team success rate is neither, so it lives
-- here. Two views, two grains, one fact family — which is the opposite of what srv_schedule
-- and srv_scoreboard were.
--
-- COVERAGE IS PARTIAL AND THE FLAGS SAY WHERE. The four sources cover 1,849 to 3,339 games
-- against 110,879 in the spine, because box scores are `recent` scope. has_box_advanced /
-- has_team_advanced / has_havoc / has_ppa distinguish "the endpoint does not cover this game"
-- from "this team recorded nothing", which a null alone cannot.
-- ==========================================================================================
-- THE MARKET, FROM THIS TEAM'S SIDE OF THE LINE (R-260).
--
-- Marc wanted ATS and line-implied points on Scores, and neither existed at this grain:
-- srv_game carries `market_implied_home_points` / `_away_points` at GAME grain and
-- `winner_covered_close` as a verdict about the winner, not about a team. A game x team sheet
-- needs the number from the row's own perspective.
--
-- THE SIGN DOES ALL THE WORK, AND IT IS THE SAME IDENTITY R-201 VERIFIED.
-- `spread` is home-perspective and negative favours home, so with
--     team_spread = spread for the home row, -spread for the away row
-- BOTH derived values fall out with no branch anywhere:
--     line-implied points = (total - team_spread) / 2
--     ATS margin          = margin + team_spread          (positive means covered)
-- For the home row the first is R-201's `(total - spread) / 2` unchanged; for the away row it
-- becomes `(total + spread) / 2`, which is the other half of the same identity. One CASE, at
-- the top, and nothing downstream has to know which side of the game it is on.
--
-- WHICH LINE. "Finished" is the lock rule srv_game already uses — the closing number once it
-- exists, the live one before that — so the two views cannot disagree about what the line was.
-- "Open" is the opening number as recorded.
with market as (

    select game_id,
           coalesce(spread_at_close, spread_current) as spread_final,
           coalesce(total_at_close,  total_current)  as total_final,
           spread_open,
           over_under_open                           as total_open
    from {{ ref('fct_game_market') }}

),

team_line as (

    select
        g.game_team_sk,
        g.margin,
        g.points_for,
        g.is_completed,
        case when g.is_home then m.spread_final else -m.spread_final end as spread_final,
        case when g.is_home then m.spread_open  else -m.spread_open  end as spread_open,
        m.total_final,
        m.total_open
    from {{ ref('fct_game_team') }} g
    left join market m on m.game_id = g.game_id

),

team_market_raw as (

    select
        game_team_sk,
        margin,
        points_for,
        is_completed,
        spread_final,
        spread_open,
        total_final,
        total_open,
        (total_final - spread_final) / 2.0 as line_implied_points_final,
        (total_open  - spread_open)  / 2.0 as line_implied_points_open,
        margin + spread_final              as ats_margin_final,
        margin + spread_open               as ats_margin_open
    from team_line

),

team_market as (

    -- EVERY `_open` COLUMN IS NULL WHEN IT EQUALS ITS CLOSING COUNTERPART (Marc: "only
    -- calculate it for opening line if it's different than the ending line"). Applied per
    -- column rather than per game, so a column is blank exactly when it would have repeated
    -- the value immediately to its left, and populated whenever it carries something new.
    --
    -- Worth knowing before reading a file: this suppresses less than it sounds. In 2025 the
    -- spread moved on 753 of 888 FBS games and the total on 756 — the open half is populated
    -- about 85% of the time, so a blank there is a genuine "the market never changed its
    -- mind", not the common case.
    select
        game_team_sk,
        spread_final,
        total_final,
        line_implied_points_final,
        points_for - line_implied_points_final as points_vs_line_implied_final,
        ats_margin_final,
        case when spread_final is null then null
             when not is_completed    then 'pending'
             when ats_margin_final > 0 then 'yes'
             when ats_margin_final < 0 then 'no'
             else 'push' end                   as covered_final,

        case when spread_open = spread_final then null else spread_open end
                                               as spread_open,
        case when total_open = total_final then null else total_open end
                                               as total_open,
        case when line_implied_points_open = line_implied_points_final then null
             else line_implied_points_open end as line_implied_points_open,
        case when line_implied_points_open = line_implied_points_final then null
             else points_for - line_implied_points_open end
                                               as points_vs_line_implied_open,
        case when ats_margin_open = ats_margin_final then null
             else ats_margin_open end          as ats_margin_open,
        case when spread_open is null or spread_open = spread_final then null
             when not is_completed     then 'pending'
             when ats_margin_open > 0  then 'yes'
             when ats_margin_open < 0  then 'no'
             else 'push' end                   as covered_open
    from team_market_raw

)

select
    a.game_team_advanced_sk,
    t.game_team_sk,
    t.game_id,
    t.season,
    t.week,
    t.season_type,
    t.game_date,
    t.team_id,
    t.team,
    -- fct_game_team carries classification but not conference; the conference is
    -- season-scoped and comes from dim_team, as it does on every other serving view.
    d.conference,
    t.classification,
    t.opponent_team_id,
    t.opponent,
    -- THE DIVISION FILTER NEEDS A GAME-LEVEL FACT, AND THIS VIEW ONLY HAD TEAM-LEVEL ONES.
    --
    -- `classification` is the TEAM's, so filtering on it would keep the FBS side of an
    -- FBS-vs-FCS game and drop the other — one row for a game that has two, which breaks the
    -- pairing every other thing on the Scores sheet is built on (the banding, the possession
    -- sum, the away-then-home order).
    --
    -- The predicate is srv_game.is_fbs_game's, taken literally rather than re-derived:
    -- `(home_classification = 'fbs' or away_classification = 'fbs')`. Here the same two
    -- classifications are called `classification` and `opponent_classification`, and they are
    -- symmetric across a game's two rows, so both rows agree by construction. Two spellings
    -- of one rule is how Schedule and the export drifted in R-184.
    (t.classification = 'fbs' or t.opponent_classification = 'fbs') as is_fbs_game,
    t.is_home,
    t.is_neutral_site,
    t.is_completed,
    t.points_for,
    t.points_against,
    t.margin,
    t.result,

    -- The plain box score, from fct_game_team.
    t.first_downs,
    t.total_yards,
    t.rushing_yards,
    t.passing_yards,
    t.rushing_attempts,
    t.turnovers,
    t.interceptions,
    t.fumbles_lost,
    t.third_down_conversions,
    t.third_down_attempts,
    t.fourth_down_conversions,
    t.fourth_down_attempts,
    t.penalties,
    t.penalty_yards,
    t.possession_seconds,
    t.has_box_score,

    -- Which advanced sources reached this row.
    a.has_box_advanced,
    a.has_team_advanced,
    a.has_havoc,
    a.has_ppa,

    a.plays,
    a.ppa_overall_total,
    a.ppa_overall_quarter1,
    a.ppa_overall_quarter2,
    a.ppa_overall_quarter3,
    a.ppa_overall_quarter4,
    a.ppa_passing_total,
    a.ppa_passing_quarter1,
    a.ppa_passing_quarter2,
    a.ppa_passing_quarter3,
    a.ppa_passing_quarter4,
    a.ppa_rushing_total,
    a.ppa_rushing_quarter1,
    a.ppa_rushing_quarter2,
    a.ppa_rushing_quarter3,
    a.ppa_rushing_quarter4,
    a.cumulative_ppa_overall_total,
    a.cumulative_ppa_overall_quarter1,
    a.cumulative_ppa_overall_quarter2,
    a.cumulative_ppa_overall_quarter3,
    a.cumulative_ppa_overall_quarter4,
    a.cumulative_ppa_passing_total,
    a.cumulative_ppa_passing_quarter1,
    a.cumulative_ppa_passing_quarter2,
    a.cumulative_ppa_passing_quarter3,
    a.cumulative_ppa_passing_quarter4,
    a.cumulative_ppa_rushing_total,
    a.cumulative_ppa_rushing_quarter1,
    a.cumulative_ppa_rushing_quarter2,
    a.cumulative_ppa_rushing_quarter3,
    a.cumulative_ppa_rushing_quarter4,
    a.success_rate_overall_total,
    a.success_rate_overall_quarter1,
    a.success_rate_overall_quarter2,
    a.success_rate_overall_quarter3,
    a.success_rate_overall_quarter4,
    a.success_rate_standard_downs_total,
    a.success_rate_standard_downs_quarter1,
    a.success_rate_standard_downs_quarter2,
    a.success_rate_standard_downs_quarter3,
    a.success_rate_standard_downs_quarter4,
    a.success_rate_passing_downs_total,
    a.success_rate_passing_downs_quarter1,
    a.success_rate_passing_downs_quarter2,
    a.success_rate_passing_downs_quarter3,
    a.success_rate_passing_downs_quarter4,
    a.explosiveness_total,
    a.explosiveness_quarter1,
    a.explosiveness_quarter2,
    a.explosiveness_quarter3,
    a.explosiveness_quarter4,
    a.power_success,
    a.stuff_rate,
    a.line_yards,
    a.line_yards_average,
    a.second_level_yards,
    a.second_level_yards_average,
    a.open_field_yards,
    a.open_field_yards_average,
    a.havoc_total,
    a.havoc_front_seven,
    a.havoc_db,
    a.scoring_opportunities,
    a.scoring_opportunity_points,
    a.points_per_opportunity,
    a.average_start,
    a.average_starting_predicted_points,
    a.offense_plays,
    a.offense_drives,
    a.offense_ppa,
    a.offense_total_ppa,
    a.offense_success_rate,
    a.offense_explosiveness,
    a.offense_power_success,
    a.offense_stuff_rate,
    a.offense_line_yards,
    a.offense_line_yards_total,
    a.offense_second_level_yards,
    a.offense_second_level_yards_total,
    a.offense_open_field_yards,
    a.offense_open_field_yards_total,
    a.offense_standard_downs_ppa,
    a.offense_standard_downs_success_rate,
    a.offense_standard_downs_explosiveness,
    a.offense_passing_downs_ppa,
    a.offense_passing_downs_success_rate,
    a.offense_passing_downs_explosiveness,
    a.offense_rushing_plays_ppa,
    a.offense_rushing_plays_total_ppa,
    a.offense_rushing_plays_success_rate,
    a.offense_rushing_plays_explosiveness,
    a.offense_passing_plays_ppa,
    a.offense_passing_plays_total_ppa,
    a.offense_passing_plays_success_rate,
    a.offense_passing_plays_explosiveness,
    a.defense_plays,
    a.defense_drives,
    a.defense_ppa,
    a.defense_total_ppa,
    a.defense_success_rate,
    a.defense_explosiveness,
    a.defense_power_success,
    a.defense_stuff_rate,
    a.defense_line_yards,
    a.defense_line_yards_total,
    a.defense_second_level_yards,
    a.defense_second_level_yards_total,
    a.defense_open_field_yards,
    a.defense_open_field_yards_total,
    a.defense_standard_downs_ppa,
    a.defense_standard_downs_success_rate,
    a.defense_standard_downs_explosiveness,
    a.defense_passing_downs_ppa,
    a.defense_passing_downs_success_rate,
    a.defense_passing_downs_explosiveness,
    a.defense_rushing_plays_ppa,
    a.defense_rushing_plays_total_ppa,
    a.defense_rushing_plays_success_rate,
    a.defense_rushing_plays_explosiveness,
    a.defense_passing_plays_ppa,
    a.defense_passing_plays_total_ppa,
    a.defense_passing_plays_success_rate,
    a.defense_passing_plays_explosiveness,
    a.opponent_conference,
    a.offense_total_plays,
    a.offense_total_havoc_events,
    a.offense_front_seven_havoc_events,
    a.offense_db_havoc_events,
    a.offense_havoc_rate,
    a.offense_front_seven_havoc_rate,
    a.offense_db_havoc_rate,
    a.defense_total_plays,
    a.defense_total_havoc_events,
    a.defense_front_seven_havoc_events,
    a.defense_db_havoc_events,
    a.defense_havoc_rate,
    a.defense_front_seven_havoc_rate,
    a.defense_db_havoc_rate,
    a.offense_overall,
    a.offense_passing,
    a.offense_rushing,
    a.offense_first_down,
    a.offense_second_down,
    a.offense_third_down,
    a.defense_overall,
    a.defense_passing,
    a.defense_rushing,
    a.defense_first_down,
    a.defense_second_down,
    a.defense_third_down,
    mk.spread_final,
    mk.total_final,
    mk.line_implied_points_final,
    mk.points_vs_line_implied_final,
    mk.ats_margin_final,
    mk.covered_final,
    mk.spread_open,
    mk.total_open,
    mk.line_implied_points_open,
    mk.points_vs_line_implied_open,
    mk.ats_margin_open,
    mk.covered_open
from {{ ref('fct_game_team') }} t
join {{ ref('fct_game_team_advanced') }} a on a.game_team_sk = t.game_team_sk
left join {{ ref('dim_team') }} d on d.season = t.season and d.team_id = t.team_id
-- LEFT, not inner: a Division III fixture has no line and must keep its row. An inner join
-- here would silently narrow the view to games a sportsbook priced.
left join team_market mk on mk.game_team_sk = t.game_team_sk
