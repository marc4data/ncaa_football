-- Player usage share for a season: one row per (season, player).
--
-- The share of a team's plays a player was involved in, split by down and play type. Pairs
-- naturally with stg_player_season_ppa — usage is how often, PPA is how well — and the two
-- share the same key.
--
-- IT ALSO SHARES THAT MODEL'S CONFERENCE QUIRK. /player/usage reports `B1G`, `B12`, `AAC`
-- where /ppa/teams, /ratings/* and most others report full names. The column is named
-- `conference_abbreviation` for the same reason: a join written against `conference` should
-- fail to compile rather than silently return nothing.

{% set splits = ['overall', 'pass', 'rush', 'firstDown', 'secondDown', 'thirdDown',
                 'standardDowns', 'passingDowns'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_player_usage') }}
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
                    {{ json_get_string('row_json', 'season') }},
                    {{ json_get_string('row_json', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'id') }}                  as player_id,
    {{ json_get_string('row_json', 'name') }}                as player_name,
    {{ json_get_string('row_json', 'position') }}            as position,
    {{ json_get_string('row_json', 'team') }}                as team,
    -- ABBREVIATED on this endpoint, as on /ppa/players/season. See the header.
    {{ json_get_string('row_json', 'conference') }}          as conference_abbreviation

{%- for metric in splits %},
    {{ safe_numeric(json_get_nested_string('row_json', ['usage', metric])) }}
        as usage_{{ snake_case(metric) }}
{%- endfor %}

from deduped
