-- Team PPA for a season: one row per (season, team), offense and defense side by side.
--
-- Predicted Points Added — the expected-points value a play adds — averaged per play and
-- accumulated over the season. Split by pass/rush and by down, for both sides of the ball.
--
-- ALONGSIDE stg_team_rating, WHICH TAKES `offense.overall` AND NOTHING ELSE. That model
-- conforms five ratings endpoints to a comparable shape and PPA's nine other fields have
-- nowhere to go in it: three of ten survived. Same split of responsibility as the ratings
-- family — conforming is a mart's job, representing the endpoint is staging's.
--
-- TWO SCALES IN ONE PAYLOAD. The flat metrics are PER-PLAY averages; `cumulative` is the
-- season TOTAL. `offense_overall` of 0.13 and `offense_cumulative_total` of 104.5 are the
-- same statistic at different scales, and the prefix is what keeps a chart from plotting
-- them on one axis.
--
-- DEFENSIVE PPA IS NOT INVERTED HERE. A defence allowing 0.19 PPA per play is worse than one
-- allowing 0.10, so lower is better on the defensive columns and higher is better on the
-- offensive ones. CFBD publishes it that way and staging keeps it that way; flipping the sign
-- would be an interpretation, and one that silently disagrees with the API's own numbers.

{% set splits = ['overall', 'passing', 'rushing', 'firstDown', 'secondDown', 'thirdDown'] %}
{% set cumulative = ['total', 'passing', 'rushing'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ppa_teams') }}
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
    {%- for metric in splits %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
    {%- for metric in cumulative %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, 'cumulative', metric])) }}
        as {{ side }}_cumulative_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %}

from deduped
