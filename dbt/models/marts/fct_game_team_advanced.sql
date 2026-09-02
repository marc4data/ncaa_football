{{ config(materialized='table') }}

-- Advanced team performance, one row per (game, team). R-077.
--
-- WHY THIS IS A SEPARATE MART RATHER THAN COLUMNS ON fct_game_team, which is the shape
-- question prompt 030 asked to have answered before building:
--
-- fct_game_team is 221,758 rows covering every game in the warehouse back to 1869. These
-- four sources cover 1,849 to 3,339 games each — box scores are `recent` scope. Folding 172
-- measure columns onto that fact would produce a 216-column table that is null on roughly
-- 98% of its rows, and every consumer of the plain box score would pay to scan them.
--
-- Separate mart, same grain, left-joined where wanted. srv_game_team is where they meet.
--
-- THE NAME JOIN IS CLEAN, WHICH WAS NOT A SAFE ASSUMPTION. All four key on (game_id, team)
-- BY NAME — the trap flagged for /teams/matchup, where a season-scoped team map silently
-- drops renamed schools. Measured against fct_game_team: 3,698 / 6,678 / 4,587 / 3,469 rows
-- respectively, ALL AT 100.00%. Nothing is dropped. That holds because both sides carry
-- CFBD's own spelling within the same game, not because names are stable in general.
--
-- Five columns collide across the four sources — season, season_type, week, opponent,
-- conference — and all five are CONTEXT, not measures. They are taken from fct_game_team
-- instead, so the game spine remains the single source for what game this was.

with box as (select * from {{ ref('stg_game_box_team') }}),
     adv as (select * from {{ ref('stg_game_team_advanced') }}),
     hav as (select * from {{ ref('stg_game_team_havoc') }}),
     ppa as (select * from {{ ref('stg_game_team_ppa') }})

select
    {{ surrogate_key(['g.game_id', 'g.team_id']) }} as game_team_advanced_sk,
    g.game_team_sk,
    g.game_id,
    g.team_id,
    g.team,
    g.season,
    g.season_type,
    g.week,
    g.opponent,
    -- Which sources actually reached this row. Absence here means the endpoint does not cover
    -- the game, not that the team recorded nothing.
    box.game_id is not null as has_box_advanced,
    adv.game_id is not null as has_team_advanced,
    hav.game_id is not null as has_havoc,
    ppa.game_id is not null as has_ppa,

    -- stg_game_box_team — 67 measure column(s)
    box.plays,
    box.ppa_overall_total,
    box.ppa_overall_quarter1,
    box.ppa_overall_quarter2,
    box.ppa_overall_quarter3,
    box.ppa_overall_quarter4,
    box.ppa_passing_total,
    box.ppa_passing_quarter1,
    box.ppa_passing_quarter2,
    box.ppa_passing_quarter3,
    box.ppa_passing_quarter4,
    box.ppa_rushing_total,
    box.ppa_rushing_quarter1,
    box.ppa_rushing_quarter2,
    box.ppa_rushing_quarter3,
    box.ppa_rushing_quarter4,
    box.cumulative_ppa_overall_total,
    box.cumulative_ppa_overall_quarter1,
    box.cumulative_ppa_overall_quarter2,
    box.cumulative_ppa_overall_quarter3,
    box.cumulative_ppa_overall_quarter4,
    box.cumulative_ppa_passing_total,
    box.cumulative_ppa_passing_quarter1,
    box.cumulative_ppa_passing_quarter2,
    box.cumulative_ppa_passing_quarter3,
    box.cumulative_ppa_passing_quarter4,
    box.cumulative_ppa_rushing_total,
    box.cumulative_ppa_rushing_quarter1,
    box.cumulative_ppa_rushing_quarter2,
    box.cumulative_ppa_rushing_quarter3,
    box.cumulative_ppa_rushing_quarter4,
    box.success_rate_overall_total,
    box.success_rate_overall_quarter1,
    box.success_rate_overall_quarter2,
    box.success_rate_overall_quarter3,
    box.success_rate_overall_quarter4,
    box.success_rate_standard_downs_total,
    box.success_rate_standard_downs_quarter1,
    box.success_rate_standard_downs_quarter2,
    box.success_rate_standard_downs_quarter3,
    box.success_rate_standard_downs_quarter4,
    box.success_rate_passing_downs_total,
    box.success_rate_passing_downs_quarter1,
    box.success_rate_passing_downs_quarter2,
    box.success_rate_passing_downs_quarter3,
    box.success_rate_passing_downs_quarter4,
    box.explosiveness_total,
    box.explosiveness_quarter1,
    box.explosiveness_quarter2,
    box.explosiveness_quarter3,
    box.explosiveness_quarter4,
    box.power_success,
    box.stuff_rate,
    box.line_yards,
    box.line_yards_average,
    box.second_level_yards,
    box.second_level_yards_average,
    box.open_field_yards,
    box.open_field_yards_average,
    box.havoc_total,
    box.havoc_front_seven,
    box.havoc_db,
    box.scoring_opportunities,
    box.scoring_opportunity_points,
    box.points_per_opportunity,
    box.average_start,
    box.average_starting_predicted_points,

    -- stg_game_team_advanced — 56 measure column(s)
    adv.offense_plays,
    adv.offense_drives,
    adv.offense_ppa,
    adv.offense_total_ppa,
    adv.offense_success_rate,
    adv.offense_explosiveness,
    adv.offense_power_success,
    adv.offense_stuff_rate,
    adv.offense_line_yards,
    adv.offense_line_yards_total,
    adv.offense_second_level_yards,
    adv.offense_second_level_yards_total,
    adv.offense_open_field_yards,
    adv.offense_open_field_yards_total,
    adv.offense_standard_downs_ppa,
    adv.offense_standard_downs_success_rate,
    adv.offense_standard_downs_explosiveness,
    adv.offense_passing_downs_ppa,
    adv.offense_passing_downs_success_rate,
    adv.offense_passing_downs_explosiveness,
    adv.offense_rushing_plays_ppa,
    adv.offense_rushing_plays_total_ppa,
    adv.offense_rushing_plays_success_rate,
    adv.offense_rushing_plays_explosiveness,
    adv.offense_passing_plays_ppa,
    adv.offense_passing_plays_total_ppa,
    adv.offense_passing_plays_success_rate,
    adv.offense_passing_plays_explosiveness,
    adv.defense_plays,
    adv.defense_drives,
    adv.defense_ppa,
    adv.defense_total_ppa,
    adv.defense_success_rate,
    adv.defense_explosiveness,
    adv.defense_power_success,
    adv.defense_stuff_rate,
    adv.defense_line_yards,
    adv.defense_line_yards_total,
    adv.defense_second_level_yards,
    adv.defense_second_level_yards_total,
    adv.defense_open_field_yards,
    adv.defense_open_field_yards_total,
    adv.defense_standard_downs_ppa,
    adv.defense_standard_downs_success_rate,
    adv.defense_standard_downs_explosiveness,
    adv.defense_passing_downs_ppa,
    adv.defense_passing_downs_success_rate,
    adv.defense_passing_downs_explosiveness,
    adv.defense_rushing_plays_ppa,
    adv.defense_rushing_plays_total_ppa,
    adv.defense_rushing_plays_success_rate,
    adv.defense_rushing_plays_explosiveness,
    adv.defense_passing_plays_ppa,
    adv.defense_passing_plays_total_ppa,
    adv.defense_passing_plays_success_rate,
    adv.defense_passing_plays_explosiveness,

    -- stg_game_team_havoc — 15 measure column(s)
    hav.opponent_conference,
    hav.offense_total_plays,
    hav.offense_total_havoc_events,
    hav.offense_front_seven_havoc_events,
    hav.offense_db_havoc_events,
    hav.offense_havoc_rate,
    hav.offense_front_seven_havoc_rate,
    hav.offense_db_havoc_rate,
    hav.defense_total_plays,
    hav.defense_total_havoc_events,
    hav.defense_front_seven_havoc_events,
    hav.defense_db_havoc_events,
    hav.defense_havoc_rate,
    hav.defense_front_seven_havoc_rate,
    hav.defense_db_havoc_rate,

    -- stg_game_team_ppa — 12 measure column(s)
    ppa.offense_overall,
    ppa.offense_passing,
    ppa.offense_rushing,
    ppa.offense_first_down,
    ppa.offense_second_down,
    ppa.offense_third_down,
    ppa.defense_overall,
    ppa.defense_passing,
    ppa.defense_rushing,
    ppa.defense_first_down,
    ppa.defense_second_down,
    ppa.defense_third_down
from {{ ref('fct_game_team') }} g
left join box on box.game_id = g.game_id and box.team = g.team
left join adv on adv.game_id = g.game_id and adv.team = g.team
left join hav on hav.game_id = g.game_id and hav.team = g.team
left join ppa on ppa.game_id = g.game_id and ppa.team = g.team
