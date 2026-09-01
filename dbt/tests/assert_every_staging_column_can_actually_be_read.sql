-- Every column of every staging model must survive being selected.
--
-- THE BUG THIS EXISTS FOR PASSED EVERY OTHER TEST IN THE PROJECT.
--
-- stg_recruit cast /recruiting/players' `height` to int. That endpoint reports half-inches —
-- 74.5, 79.5 — on 1,033 rows, and an int cast does not round them, it RAISES. The view could
-- not be read at all: any query touching the column failed with "invalid input syntax for
-- type integer: 79.5".
--
-- It survived for months because POSTGRES PRUNES UNREFERENCED COLUMNS OUT OF A VIEW'S TARGET
-- LIST. count(*) references no column, so the uniqueness sweep, the not-silently-empty sweep
-- and every not_null test built their plans without the broken expression and passed. The
-- model was green, materialised, documented, and unreadable. It surfaced only when a person
-- tried to export the data.
--
-- THIS TEST IS UNUSUAL AND THE SHAPE IS DELIBERATE. The predicate can never be true — count()
-- does not return null. The assertion is not the WHERE clause, it is the EVALUATION: casting
-- each row to text forces every output column to be computed, so a column that cannot be read
-- makes this query ERROR and dbt fails the build with the offending value in the message. A
-- test that returns rows cannot express "this does not run against real data"; only running
-- it can.
--
-- count(x::text) rather than count(*) for exactly the reason above. The first sweep that
-- found this used count(*) over a subquery selecting x::text, and Postgres pruned that too —
-- the trick was defeated by the mechanism it was written to defeat.
--
-- THE LIST IS EXPLICIT BECAUSE ref() CANNOT LIVE IN A CONDITIONAL. Enumerating the models
-- from dbt's graph fails to parse: the graph is empty at parse time, so dbt cannot infer the
-- dependencies. test_the_staging_readability_sweep_covers_every_model keeps this list honest
-- against the files on disk, so a new model cannot quietly escape the sweep.
--
-- Cost is about a minute across these models, measured: 21 seconds for the 1.45M-row
-- stg_player_season_stat and 23 for the 583k-row stg_play, the rest far smaller. That is a
-- real cost and it buys the one property no other test here can see.
-- TAGGED slow_sweep, AND NOT full_refresh_only — THE DISTINCTION IS THE POINT.
--
-- full_refresh_only means "this DAG CANNOT SATISFY this test": it straddles the refresh
-- boundary, comparing something the scores DAG refreshes against something it does not, so
-- running it there reports a fetch-time gap as a failure.
-- test_single_sided_tests_keep_their_coverage_in_the_scores_dag enforces that meaning, and
-- it caught the first version of this file borrowing the tag.
--
-- This test CAN be satisfied every two hours. It is excluded for COST, which is a different
-- reason and gets a different tag. Measured at 134 seconds against production: the scores DAG
-- runs twelve times a day to move scores and lines quickly, its selector reaches these models
-- as ancestors, and adding two and a quarter minutes there to re-check a property that only
-- changes when a MODEL changes would be paying a lot for nothing. The weekly full build is
-- where it belongs.
{{ config(tags=['slow_sweep']) }}

{% set staging_models = [
    'stg_api_quota',
    'stg_api_recent_request',
    'stg_api_usage_endpoint',
    'stg_calendar',
    'stg_cfp_bracket',
    'stg_cfp_matchup',
    'stg_cfp_participant',
    'stg_coach_season',
    'stg_coach_season_detail',
    'stg_conference_affiliation',
    'stg_conference_change',
    'stg_conferences',
    'stg_dbt_test_result',
    'stg_deploy_status',
    'stg_draft_pick',
    'stg_draft_position',
    'stg_drive',
    'stg_field_goal_ep',
    'stg_game_box_info',
    'stg_game_box_player',
    'stg_game_box_team',
    'stg_game_media',
    'stg_game_player_stat',
    'stg_game_pregame_wp',
    'stg_game_team_advanced',
    'stg_game_team_havoc',
    'stg_game_team_ppa',
    'stg_game_team_stat',
    'stg_game_weather',
    'stg_game_win_probability',
    'stg_games',
    'stg_lines',
    'stg_nfl_team',
    'stg_passing_play',
    'stg_passing_player_game',
    'stg_passing_player_season',
    'stg_passing_team_game',
    'stg_passing_team_season',
    'stg_play',
    'stg_play_stat',
    'stg_play_stat_type',
    'stg_play_type',
    'stg_player_game_ppa',
    'stg_player_game_success',
    'stg_player_portal',
    'stg_player_season_ppa',
    'stg_player_season_stat',
    'stg_player_season_success',
    'stg_player_season_usage',
    'stg_player_season_wepa_kicking',
    'stg_player_season_wepa_passing',
    'stg_player_season_wepa_rushing',
    'stg_predictions',
    'stg_rankings',
    'stg_rating_core',
    'stg_rating_elo',
    'stg_rating_fpi',
    'stg_rating_sp',
    'stg_rating_sp_conference',
    'stg_rating_srs',
    'stg_rating_srs_expanded',
    'stg_raw_manifest',
    'stg_recruit',
    'stg_roster',
    'stg_stat_category',
    'stg_team_fbs',
    'stg_team_rating',
    'stg_team_record',
    'stg_team_recruiting_position_group',
    'stg_team_recruiting_rank',
    'stg_team_returning_production',
    'stg_team_season_advanced',
    'stg_team_season_ats',
    'stg_team_season_ppa',
    'stg_team_season_stat',
    'stg_team_season_wepa',
    'stg_team_talent',
    'stg_teams',
    'stg_venues',
    'stg_warehouse_usage',
] %}

with readable as (
    {% for model in staging_models %}
    select '{{ model }}' as model_name, count(x::text) as readable_rows
    from {{ ref(model) }} x
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)
select model_name, readable_rows
from readable
where readable_rows is null
