-- Opponent-adjusted kicking value per player: one row per (season, athlete).
--
-- THE ODD ONE OF THE THREE, IN TWO WAYS, AND NEITHER IS RENAMED HERE.
--
-- The metric is `paar`, not `wepa` — Points Above Average Replacement, a different statistic
-- on a different scale from the passing and rushing models' wEPA. Calling the column `wepa`
-- for symmetry would make three models look unionable when their measures are not
-- comparable; a chart stacking them would be meaningless and would look fine.
--
-- The denominator is `attempts`, not `plays`, and there is NO `position` column — every row
-- is a kicker, so the endpoint omits it. Inventing one would be inventing data.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_wepa_players_kicking') }}
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
                    {{ json_get_string('row_json', 'athleteId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'year') }} as int)     as season,
    {{ json_get_string('row_json', 'athleteId') }}             as athlete_id,
    {{ json_get_string('row_json', 'athleteName') }}           as athlete_name,
    {{ json_get_string('row_json', 'team') }}                  as team,
    {{ json_get_string('row_json', 'conference') }}            as conference,
    -- Points Above Average Replacement. NOT wEPA; see the header.
    {{ safe_numeric(json_get_string('row_json', 'paar')) }}    as paar,
    cast({{ json_get_string('row_json', 'attempts') }} as int) as attempts
from deduped
