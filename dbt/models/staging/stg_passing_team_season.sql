-- Team passing for a season: one row per (season, team), offense and defense side by side.
--
-- Same thirteen measures as the player models, nested under `offense` and `defense` rather
-- than flat — so both sides are generated from one list and a `defense_attempts` reading
-- `offense.attempts` is unrepresentable.
--
-- DEFENSE HERE IS PASSING ALLOWED. `defense_completion_rate` is the rate opposing passers
-- achieved against this team, so LOWER is better on every defensive column and higher is
-- better on every offensive one. Not inverted, matching how CFBD publishes it and how the
-- ppa and wepa models treat the same asymmetry.
--
-- Availability caveat as ever: see macros/passing.sql.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_passing_teams_season') }}
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
                    {{ json_get_string('row_json', 'team') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'season') }} as int) as season,
    {{ json_get_string('row_json', 'team') }}                as team,
    {{ json_get_string('row_json', 'conference') }}          as conference

{%- for side in ['offense', 'defense'] %}
    {%- for metric in passing_metrics() %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
