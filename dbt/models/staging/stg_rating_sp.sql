-- SP+ team ratings: one row per (season, team), offense / defense / special teams.
--
-- WHY THIS EXISTS ALONGSIDE stg_team_rating. That model UNIONS five ratings endpoints into
-- one conformed long shape — season, team, rating_system, rating, ranking — because
-- fct_team_rating needs them comparable. Conforming means keeping the columns the five have
-- in common and dropping the rest, so SP+'s twelve component metrics had nowhere to go: six
-- of eighteen fields survived.
--
-- Those are two different jobs. Conforming is a MART's job and stg_team_rating does it well;
-- representing an endpoint faithfully is staging's, and nothing was doing it. This model does
-- the second, stg_team_rating is untouched, and the two coexist — the coverage matrix reads
-- the union of every model over a raw table, so the endpoint now counts as complete.
--
-- `year`, NOT `season`, ON THE WIRE. Every ratings endpoint spells it `year`; the column is
-- named `season` here so it matches every other staging model and can be joined without a
-- translation step. The lookup keeps the wire spelling.
--
-- MOST COMPONENT METRICS ARE NULL FOR RECENT SEASONS. In the landed 2024 data `rating` and
-- `ranking` are populated while `success`, `explosiveness`, `rushing` and the rest are not —
-- CFBD publishes the components for older seasons and has not backfilled them. They are
-- carried anyway: a column that is null today and populated in a 2015 backfill tomorrow is
-- worth having, and the alternative is discovering the endpoint had them all along.

{% set shared = ['rating', 'success', 'explosiveness', 'rushing', 'passing',
                 'standardDowns', 'passingDowns'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_ratings_sp') }}
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
    cast({{ json_get_string('row_json', 'year') }} as int)  as season,
    {{ json_get_string('row_json', 'team') }}               as team,
    {{ json_get_string('row_json', 'conference') }}         as conference,

    {{ safe_numeric(json_get_string('row_json', 'rating')) }}          as rating,
    cast({{ json_get_string('row_json', 'ranking') }} as int)          as ranking,
    {{ safe_numeric(json_get_string('row_json', 'secondOrderWins')) }} as second_order_wins,
    {{ safe_numeric(json_get_string('row_json', 'sos')) }}             as strength_of_schedule

{%- for side in ['offense', 'defense'] %}
    ,
    cast({{ json_get_nested_string('row_json', [side, 'ranking']) }} as int)
        as {{ side }}_ranking
    {%- for metric in shared %},
    {{ safe_numeric(json_get_nested_string('row_json', [side, metric])) }}
        as {{ side }}_{{ snake_case(metric) }}
    {%- endfor %}
{%- endfor %},

    -- Offense-only: pace and run rate describe how an offense operates, and have no
    -- defensive counterpart in the payload.
    {{ safe_numeric(json_get_nested_string('row_json', ['offense', 'runRate'])) }} as offense_run_rate,
    {{ safe_numeric(json_get_nested_string('row_json', ['offense', 'pace'])) }}    as offense_pace,

    -- Defense-only: havoc is a defensive concept here, nested one level deeper.
    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'total'])) }}
        as defense_havoc_total,
    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'frontSeven'])) }}
        as defense_havoc_front_seven,
    {{ safe_numeric(json_get_nested_string('row_json', ['defense', 'havoc', 'db'])) }}
        as defense_havoc_db,

    {{ safe_numeric(json_get_nested_string('row_json', ['specialTeams', 'rating'])) }}
        as special_teams_rating
from deduped
