-- Every staging model holds one row per the grain its documentation claims.
--
-- WHY STAGING NEEDS THIS AND NOT JUST THE FACTS. Staging is where the raw layer's
-- multiplicity is resolved, so it is where the resolution can be wrong, and a duplicate
-- introduced here is inherited by every mart downstream. The fact-level sweep
-- (assert_facts_are_unique_on_their_natural_key) catches the consequence one layer late,
-- after the fan-out has already been joined into something.
--
-- THE SPECIFIC FAILURE THIS EXISTS FOR. Staging models dedup with
-- `row_number() over (partition by params ...)`, which keeps the newest response PER REQUEST.
-- That is correct only while different requests return disjoint entities. It held for /games
-- until a season-scoped fetch was added next to the week-scoped ones; the two overlapped,
-- params-level dedup could not see it, and 211 duplicate game_ids reached fct_game. The fix
-- was a second dedup on the entity id — but the same shape is present in every model that
-- partitions by params, and nothing was watching the others.
--
-- Checked when this test was written, against the landed corpus: /games/teams held 3,414
-- games across 35 param sets and /games/players 3,413, with no id appearing in two fetches.
-- Disjoint TODAY. This is the tripwire for the day a season-scoped fetch is added.
--
-- Enumerating the class rather than testing one model at a time is deliberate. Six separate
-- outages in four days came from patching one instance of a defect class at a time; the
-- lesson recorded then was to enumerate the class before the third patch.
--
-- stg_rating_core DECLARES FOUR KEYS, NOT TWO. /ratings/core publishes the rating AS OF a
-- point in the season, so its grain is (season, team, through_season_type, through_week).
-- The landed data holds exactly one as-of point per season today, which is precisely the
-- condition under which a (season, team) declaration passes every build and starts silently
-- dropping rows the moment CFBD serves a second one.
--
-- Note for anyone editing the list below: it is a single Jinja expression, so NO comment
-- syntax works inside it — neither `--` nor `{# #}`. Both are compilation errors. Comments
-- about individual entries belong up here.
{% set staging_grains = [
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
] %}

{% for model, grain in staging_grains %}
select
    '{{ model }}'                                 as model_name,
    '{{ grain | join(", ") }}'                    as grain,
    count(*)                                      as duplicate_keys
from (
    select {{ grain | join(', ') }}
    from {{ ref(model) }}
    group by {{ grain | join(', ') }}
    having count(*) > 1
) d
having count(*) > 0
{% if not loop.last %}
union all
{% endif %}
{% endfor %}
