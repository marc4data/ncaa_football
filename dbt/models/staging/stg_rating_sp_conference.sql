-- SP+ at CONFERENCE grain: one row per (season, conference).
--
-- The same metric set as stg_rating_sp with the team dimension collapsed — and no `ranking`
-- anywhere, on either side or overall, because CFBD does not rank conferences here. That
-- absence is the reason this is its own model rather than a union with the team-grain one:
-- the two have different keys and different columns, and forcing them together would mean a
-- ranking column that is null for every conference row and a team column that is null for
-- every conference row.

{% set shared = ['rating', 'success', 'explosiveness', 'rushing', 'passing',
                 'standardDowns', 'passingDowns'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_sp_conferences') }}
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
                    {{ json_get_string('row_json', 'conference') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int) as season,
    {{ json_get_string('row_json', 'conference') }}        as conference,

    {{ safe_numeric(json_get_string('row_json', 'rating')) }}          as rating,
    {{ safe_numeric(json_get_string('row_json', 'secondOrderWins')) }} as second_order_wins,
    {{ safe_numeric(json_get_string('row_json', 'sos')) }}             as strength_of_schedule

{%- for side in ['offense', 'defense'] %}
    {%- for metric in shared %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %},

    {{ safe_numeric(json_get_nested_string('row_json', ['offense', 'runRate'])) }} as offense_run_rate,
    {{ safe_numeric(json_get_nested_string('row_json', ['offense', 'pace'])) }}    as offense_pace,

    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'total'])) }}
        as defense_havoc_total,
    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'frontSeven'])) }}
        as defense_havoc_front_seven,
    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'db'])) }}
        as defense_havoc_db,

    {{ safe_numeric(json_get_nested_string('row_json', ['specialTeams', 'rating'])) }}
        as special_teams_rating
from deduped
