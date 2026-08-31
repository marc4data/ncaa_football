-- A staging model whose source has data must not be empty.
--
-- THE FAILURE THIS EXISTS FOR IS SILENT BY CONSTRUCTION. stg_game_pregame_wp joined
-- raw_manifest on `endpoint = 'metrics/wp/pregame'` when the manifest keys endpoints with
-- underscores — `metrics_wp_pregame`, from src.endpoints.Endpoint.key. The join matched
-- nothing, the model returned zero rows, and the full build stayed GREEN: not_null,
-- unique and every grain assertion pass vacuously on an empty table. It was caught by
-- reading a row count by hand, which is not a control.
--
-- Every test this project has is of the form "no row breaks this rule". None of them can
-- see the absence of rows, so a model that silently produces nothing is invisible to all
-- of them at once. This is the one assertion pointed the other way.
--
-- CONDITIONAL ON THE SOURCE, not absolute. An endpoint that has never been fetched has an
-- empty raw table and an empty model, and that is correct rather than broken — the coverage
-- matrix reports it as "no raw data". The test only fires where raw HAS successful
-- responses and the model still came back with nothing.
--
-- The pairs below are generated from the `source('raw', ...)` references in the models
-- themselves; a model reading several sources is listed against the first, which is enough
-- to establish that it had something to read.
-- OPS SOURCES ARE OUT OF SCOPE. raw_model_prediction, raw_deploy_status,
-- raw_warehouse_usage and raw_dbt_test_result are written by our own jobs rather than by the
-- HTTP fetcher, so they carry no status_code and "a successful response" means nothing for
-- them. The four models over them — stg_dbt_test_result, stg_deploy_status,
-- stg_predictions and stg_warehouse_usage — are excluded rather than special-cased in
-- the predicate.
{% set model_sources = [
    ('stg_calendar', 'raw_calendar'),
    ('stg_conferences', 'raw_conferences'),
    ('stg_games', 'raw_games'),
    ('stg_game_media', 'raw_games_media'),
    ('stg_game_player_stat', 'raw_games_players'),
    ('stg_game_team_stat', 'raw_games_teams'),
    ('stg_game_weather', 'raw_games_weather'),
    ('stg_api_quota', 'raw_info'),
    ('stg_api_usage_endpoint', 'raw_info_usage'),
    ('stg_lines', 'raw_lines'),
    ('stg_game_pregame_wp', 'raw_manifest'),
    ('stg_raw_manifest', 'raw_manifest'),
    ('stg_field_goal_ep', 'raw_metrics_fg_ep'),
    ('stg_player_portal', 'raw_player_portal'),
    ('stg_team_returning_production', 'raw_player_returning'),
    ('stg_player_season_usage', 'raw_player_usage'),
    ('stg_game_team_ppa', 'raw_ppa_games'),
    ('stg_player_game_ppa', 'raw_ppa_players_games'),
    ('stg_player_season_ppa', 'raw_ppa_players_season'),
    ('stg_team_rating', 'raw_ppa_teams'),
    ('stg_team_season_ppa', 'raw_ppa_teams'),
    ('stg_rankings', 'raw_rankings'),
    ('stg_rating_core', 'raw_ratings_core'),
    ('stg_rating_elo', 'raw_ratings_elo'),
    ('stg_rating_fpi', 'raw_ratings_fpi'),
    ('stg_rating_sp', 'raw_ratings_sp'),
    ('stg_rating_sp_conference', 'raw_ratings_sp_conferences'),
    ('stg_rating_srs', 'raw_ratings_srs'),
    ('stg_rating_srs_expanded', 'raw_ratings_srs_expanded'),
    ('stg_stat_category', 'raw_stats_categories'),
    ('stg_game_team_advanced', 'raw_stats_game_advanced'),
    ('stg_game_team_havoc', 'raw_stats_game_havoc'),
    ('stg_player_season_stat', 'raw_stats_player_season'),
    ('stg_player_season_success', 'raw_stats_player_success'),
    ('stg_player_game_success', 'raw_stats_player_success_game'),
    ('stg_team_season_stat', 'raw_stats_season'),
    ('stg_team_season_advanced', 'raw_stats_season_advanced'),
    ('stg_teams', 'raw_teams'),
    ('stg_team_season_ats', 'raw_teams_ats'),
    ('stg_team_fbs', 'raw_teams_fbs'),
    ('stg_venues', 'raw_venues'),
    ('stg_player_season_wepa_kicking', 'raw_wepa_players_kicking'),
    ('stg_player_season_wepa_passing', 'raw_wepa_players_passing'),
    ('stg_player_season_wepa_rushing', 'raw_wepa_players_rushing'),
    ('stg_team_season_wepa', 'raw_wepa_team_season'),
] %}

{% for model, source_table in model_sources %}
select
    '{{ model }}'                                  as model_name,
    '{{ source_table }}'                           as source_table,
    (select count(*) from {{ ref(model) }})        as model_rows,
    (select count(*) from {{ source('raw', source_table) }} where status_code = 200)
                                                   as source_responses
where (select count(*) from {{ source('raw', source_table) }} where status_code = 200) > 0
  and (select count(*) from {{ ref(model) }}) = 0
{% if not loop.last %}
union all
{% endif %}
{% endfor %}