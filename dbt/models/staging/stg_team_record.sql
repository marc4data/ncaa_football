-- Season win-loss record: one row per (season, team), split seven ways.
--
-- LANDED BUT DELIBERATELY NOT THE SOURCE OF TRUTH. _sources.yml already records why: records
-- are DERIVED from the game spine in fct_team_record, and this endpoint exists to reconcile
-- against that derivation rather than to feed it. Two independent answers to "how many games
-- did they win" is the point — assert_derived_record_matches_cfbd_records compares them.
-- This model makes that comparison possible on every field rather than just the total.
--
-- SEVEN SPLITS OF ONE SHAPE — total, conference, home, away, neutral, regular season and
-- postseason, each with games/wins/losses/ties. Generated from one list so a `home_wins`
-- reading `away.wins` cannot be written.
--
-- COVERS EVERY DIVISION, NOT JUST FBS: 668 rows for 2024 including Division III. The
-- `classification` column is what makes that filterable, and `division` is an empty STRING
-- rather than null for teams that have none — a distinction that matters to any `is null`
-- filter written against it.

{% set metrics = ['games', 'wins', 'losses', 'ties'] %}
{% set splits = {
    'total': 'total',
    'conferenceGames': 'conference',
    'homeGames': 'home',
    'awayGames': 'away',
    'neutralSiteGames': 'neutral',
    'regularSeason': 'regular_season',
    'postseason': 'postseason',
} %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_records') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as row_json
    from successful_fetches

),

deduped as (

    select row_json
    from (
        select
            row_json,
            row_number() over (
                partition by
                    {{ json_get_string('row_json', 'year') }},
                    {{ json_get_string('row_json', 'teamId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)   as season,
    cast({{ json_get_string('row_json', 'teamId') }} as int) as team_id,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'classification') }}      as classification,
    {{ json_get_string('row_json', 'conference') }}          as conference,
    -- An empty string, not null, where a team has no division. See the header.
    {{ json_get_string('row_json', 'division') }}            as division,
    {{ safe_numeric(json_get_string('row_json', 'expectedWins')) }} as expected_wins

{%- for wire, name in splits.items() %}
    {%- for metric in metrics %},
    cast({{ json_get_nested_string('row_json', [wire, metric]) }} as int)
        as {{ name }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
