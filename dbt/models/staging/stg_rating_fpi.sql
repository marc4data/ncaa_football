-- ESPN's FPI: one row per (season, team), with its resume ranks and efficiency components.
--
-- TWO KINDS OF NUMBER IN ONE PAYLOAD, AND CONFLATING THEM WOULD BE A REAL ERROR.
-- `resumeRanks` are RANKS — 1 is best, 134 is worst, lower is better. `efficiencies` are
-- RATINGS on their own scale where higher is better. Both are numeric and several share a
-- name with the other group's concept (`fpi` appears at the top level as a rating and inside
-- resumeRanks as a rank). The prefixes are load-bearing: `resume_rank_fpi` and `fpi` are not
-- the same number and averaging them together would be silently meaningless.
--
-- stg_team_rating takes `fpi` as the rating and nothing else; the ten component columns had
-- nowhere to go in a conformed shape.

{% set resume_ranks = ['strengthOfRecord', 'fpi', 'averageWinProbability',
                       'strengthOfSchedule', 'remainingStrengthOfSchedule', 'gameControl'] %}
{% set efficiencies = ['overall', 'offense', 'defense', 'specialTeams'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_fpi') }}
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
                    {{ json_get_string('row_json', 'team') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int) as season,
    {{ json_get_string('row_json', 'team') }}              as team,
    {{ json_get_string('row_json', 'conference') }}        as conference,
    {{ safe_numeric(json_get_string('row_json', 'fpi')) }} as fpi

{%- for metric in resume_ranks %},
    cast({{ json_get_nested_string('row_json', ['resumeRanks', metric]) }} as int)
        as resume_rank_{{ snake_case(metric) }}
{%- endfor %}
{%- for metric in efficiencies %},
    {{ safe_numeric(json_get_nested_string('row_json', ['efficiencies', metric])) }}
        as efficiency_{{ snake_case(metric) }}
{%- endfor %}
from deduped
