{#-
  The serving layer, as a STATIC list. R-714.

  🚨 WHY THIS EXISTS, AND IT IS NOT TIDINESS. A113 measured the failure it prevents on A106's own
  CI run: `assert_serving_columns_are_documented` ran at node 155 of 740 and PASSED in 0.07s, while
  `serving.srv_game` was not created until 683 of 740 — 528 nodes and 24 seconds later. The test
  depends on exactly one node, `dim_field_metadata`, which reads `information_schema` through a
  macro and `ref()`s nothing, so no edge ordered it after the layer it describes. It passed because
  the tables it checks did not exist yet, and the Sunday publish then stopped for four hours on a
  gap CI had already waved through twice. CLAUDE.md §3.6 is that measurement.

  ⚠️ STATIC, AND THAT IS FORCED RATHER THAN CHOSEN. `dim_field_metadata`'s own header rules out the
  obvious alternative: "Generating `-- depends_on:` edges from `graph.nodes` looks like the fix and
  cannot work: dbt collects ref edges during parsing, `graph` is only populated at execution."
  So the refs have to come from a list that exists at PARSE time.

  ✅ THE PRECEDENT IS `staging_grains()`, WHICH SOLVED THE SAME PROBLEM THE SAME WAY.
  `assert_site_facing_staging_models_are_unique_on_their_grain` ref's every model in that static
  list UNCONDITIONALLY — its own comment explains that refs inside a conditional are not inferred
  at all — and derives only the SELECTION from the graph. Static for edges, graph for selection.

  ⚠️ A HARDCODED LIST DRIFTS, WHICH IS THE WHOLE RISK OF THIS SHAPE, so it is guarded:
  `tests/test_serving_model_list.py` holds it against `dbt/models/serving/*.sql` in both
  directions. That is the same job `ci/check_publish_build_agreement.py` does for the publish list
  one layer down — a list nobody checks is a list that is wrong the first time somebody adds a
  model.
-#}

{% macro serving_models() %}
  {{ return([
    'srv_coach_team_season',
    'srv_data_dictionary',
    'srv_drive',
    'srv_edge_bucket_performance',
    'srv_edge_finder',
    'srv_game',
    'srv_game_team',
    'srv_game_team_metric_distribution',
    'srv_game_team_metric_distribution_through_prior_week',
    'srv_game_team_leader_in_this_game',
    'srv_game_team_leader_through_prior_week',
    'srv_game_team_leader_usage',
    'srv_game_win_probability_play',
    'srv_game_travel',
    'srv_game_weather',
    'srv_line_movement',
    'srv_model_performance',
    'srv_odds_board',
    'srv_player_game_log',
    'srv_player_play',
    'srv_player_stats',
    'srv_rankings',
    'srv_rankings_compare',
    'srv_standings',
    'srv_system_health',
    'srv_team_game_log',
    'srv_team_overview',
    'srv_team_rating',
    'srv_team_roster',
    'srv_team_stats',
    'srv_team_week',
    'srv_team_week_metric_distribution',
    'srv_teams_index',
    'srv_week_metric_distribution',
    'srv_week_metric_distribution_bin',
  ]) }}
{% endmacro %}
