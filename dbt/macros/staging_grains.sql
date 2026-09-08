{#-
  The staging grain list, and the split between models the site depends on and models it does
  not (R-420).

  ONE LIST, TWO CONSEQUENCES. assert_staging_models_are_unique_on_their_grain enumerated 70
  models at dbt's default severity of `error`, in a singular test, and dbt's default
  indirect_selection is `eager` -- so a test is selected when ANY of its parents is. A
  duplicate in ANY of the 70 therefore failed a gating test in BOTH two-hourly DAGs and
  stopped BOTH publishes. On 2026-09-08 that meant a duplicate in stg_draft_pick could stop
  the site from updating.

  Measured in A063: 20 of the 70 are ancestors of a `+tag:production` model. The other 50 are
  warehouse-only -- a duplicate there stops the site updating while affecting nothing it
  renders.

  Marc's ruling, 2026-09-08: the 20 keep `error`; the 50 move to `warn`. Both keep running
  everywhere and surface in the R-412 alert payload; only the consequence differs.

  ⚠️ THE SPLIT IS DERIVED FROM THE GRAPH, NOT PASTED. A hardcoded list is wrong the day a
  serving view gains an ancestor, and it is wrong in the safe-looking direction -- a model
  silently demoted to `warn` while the site now depends on it. `site_facing_staging()` walks
  depends_on from every `production`-tagged node and returns the staging models it reaches.
-#}

{% macro staging_grains() %}
  {{ return([
    ('stg_games',              ['game_id']),
    ('stg_teams',              ['season', 'team_id']),
    ('stg_venues',             ['venue_id']),
    ('stg_calendar',           ['season', 'season_type', 'week']),
    ('stg_game_weather',       ['game_id']),
    ('stg_game_team_stat',     ['game_id', 'team_id', 'stat_category']),
    ('stg_game_player_stat',   ['game_id', 'team', 'stat_category', 'stat_type', 'athlete_id']),
    ('stg_conferences',        ['season', 'conference_id']),
    ('stg_game_media',         ['game_id', 'media_type', 'outlet']),
    ('stg_rankings',           ['season', 'season_type', 'week', 'poll_name', 'team_id']),
    ('stg_team_season_stat',   ['season', 'school', 'stat_name']),
    ('stg_game_team_advanced',  ['game_id', 'team']),
    ('stg_team_season_advanced', ['season', 'team']),
    ('stg_game_team_havoc',     ['game_id', 'team']),
    ('stg_stat_category',       ['stat_category']),
    ('stg_player_season_stat',  ['season', 'player_id', 'stat_category', 'stat_type']),
    ('stg_player_season_success', ['season', 'player_id']),
    ('stg_player_game_success', ['game_id', 'player_id']),
    ('stg_rating_sp',           ['season', 'team']),
    ('stg_rating_sp_conference', ['season', 'conference']),
    ('stg_rating_fpi',          ['season', 'team']),
    ('stg_rating_srs',          ['season', 'team']),
    ('stg_rating_srs_expanded', ['season', 'team']),
    ('stg_rating_elo',          ['season', 'team']),
    ('stg_rating_core',         ['season', 'team', 'through_season_type', 'through_week']),
    ('stg_team_season_ppa',     ['season', 'team']),
    ('stg_game_team_ppa',       ['game_id', 'team']),
    ('stg_player_season_ppa',   ['season', 'player_id']),
    ('stg_player_game_ppa',     ['season', 'season_type', 'week', 'player_id']),
    ('stg_team_season_wepa',    ['season', 'team_id']),
    ('stg_player_season_wepa_passing', ['season', 'athlete_id']),
    ('stg_player_season_wepa_rushing', ['season', 'athlete_id']),
    ('stg_player_season_wepa_kicking', ['season', 'athlete_id']),
    ('stg_team_fbs',            ['season', 'team_id']),
    ('stg_team_season_ats',     ['season', 'team_id']),
    ('stg_player_portal',       ['season', 'first_name', 'last_name', 'origin_team']),
    ('stg_team_returning_production', ['season', 'team']),
    ('stg_player_season_usage', ['season', 'player_id']),
    ('stg_field_goal_ep',       ['yards_to_goal']),
    ('stg_coach_season',        ['coach_id', 'season', 'team_id']),
    ('stg_coach_season_detail', ['coach_id', 'season', 'team_id']),
    ('stg_recruit',             ['recruit_id']),
    ('stg_team_recruiting_rank', ['recruiting_class', 'team']),
    ('stg_team_recruiting_position_group', ['team', 'position_group']),
    ('stg_team_talent',         ['season', 'team']),
    ('stg_draft_pick',          ['draft_year', 'overall_pick']),
    ('stg_draft_position',      ['position_name']),
    ('stg_nfl_team',            ['display_name']),
    ('stg_team_record',         ['season', 'team_id']),
    ('stg_roster',              ['season', 'player_id', 'team']),
    ('stg_conference_affiliation', ['team_id', 'conference_id', 'start_year']),
    ('stg_conference_change',   ['team_id', 'effective_year']),
    ('stg_cfp_bracket',         ['season', 'competition']),
    ('stg_cfp_matchup',         ['season', 'matchup_id']),
    ('stg_cfp_participant',     ['season', 'team_id']),
    ('stg_play',                ['play_id']),
    ('stg_drive',               ['drive_id']),
    ('stg_play_stat',           ['play_id', 'athlete_id', 'stat_type']),
    ('stg_play_type',           ['play_type_id']),
    ('stg_play_stat_type',      ['stat_type_id']),
    ('stg_game_box_info',       ['game_id']),
    ('stg_game_box_team',       ['game_id', 'team']),
    ('stg_game_box_player',     ['game_id', 'team', 'player_name']),
    ('stg_game_win_probability', ['play_id']),
    ('stg_passing_player_season', ['season', 'player_id']),
    ('stg_passing_player_game',  ['game_id', 'player_id']),
    ('stg_passing_team_season',  ['season', 'team']),
    ('stg_passing_team_game',    ['game_id', 'team']),
    ('stg_passing_play',         ['play_id']),
    ('stg_api_recent_request',   ['api', 'endpoint', 'requested_at'])
  ]) }}
{% endmacro %}


{% macro site_facing_staging() %}
  {#- Staging models reachable, transitively, from any node tagged `production`.
      Returns a list of bare model names. Empty during parsing, which is why every caller
      must tolerate an empty list rather than treating it as "nothing is site-facing". -#}
  {% set reached = [] %}
  {% if execute %}
    {% set frontier = [] %}
    {% for uid, node in graph.nodes.items() %}
      {% if 'production' in (node.config.tags or []) or 'production' in (node.tags or []) %}
        {% do frontier.append(uid) %}
      {% endif %}
    {% endfor %}
    {#- ⚠️ A NAMESPACE, BECAUSE JINJA'S `{% set %}` DOES NOT ESCAPE A `{% for %}`.
        The first draft reassigned `frontier` inside the loop; the assignment was discarded at
        each iteration, the walk never advanced past the seed nodes, and site_facing_staging()
        returned an EMPTY LIST. Every staging model then landed in the warn half and NOTHING
        gated the publish -- a guard silently disabled, in the same commit that split it.
        `dbt compile` caught it: 0 models on the error side, 46 on the warn side. -#}
    {% set ns = namespace(frontier=frontier, seen={}) %}
    {% for _ in range(30) %}{# depth bound: the DAG is nowhere near 30 deep #}
      {% set next_frontier = [] %}
      {% for uid in ns.frontier %}
        {% if uid not in ns.seen %}
          {% do ns.seen.update({uid: true}) %}
          {% set node = graph.nodes.get(uid) %}
          {% if node %}
            {% if node.name.startswith('stg_') and node.name not in reached %}
              {% do reached.append(node.name) %}
            {% endif %}
            {% for parent in (node.depends_on.nodes or []) %}
              {% do next_frontier.append(parent) %}
            {% endfor %}
          {% endif %}
        {% endif %}
      {% endfor %}
      {% set ns.frontier = next_frontier %}
    {% endfor %}
  {% endif %}
  {{ return(reached) }}
{% endmacro %}
