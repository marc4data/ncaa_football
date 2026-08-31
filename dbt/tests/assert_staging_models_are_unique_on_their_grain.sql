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
