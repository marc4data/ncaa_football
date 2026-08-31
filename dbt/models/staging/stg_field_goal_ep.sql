-- The field-goal expected-points curve: one row per yard line.
--
-- A STATIC MODEL — /metrics/fg/ep takes no parameters and returns the same 100-row curve on
-- every call. It is the model behind "was that a good decision to kick?": for each spot on
-- the field it gives the kick distance and the expected points of attempting the field goal.
--
-- Three fields and no season, which is why the dedup partitions on nothing but the yard
-- line: there is one curve, and the newest fetch of it wins outright.
--
-- `yardsToGoal` and `distance` differ by the snap-to-hold distance and the depth of the end
-- zone, which is why a 0-yards-to-goal row still has a 17-yard kick. Both are kept: one is
-- the field position, the other is what the kicker actually faces.

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_metrics_fg_ep') }}
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
                partition by {{ json_get_string('row_json', 'yardsToGoal') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    cast({{ json_get_string('row_json', 'yardsToGoal') }} as int) as yards_to_goal,
    cast({{ json_get_string('row_json', 'distance') }} as int)    as kick_distance,
    {{ safe_numeric(json_get_string('row_json', 'expectedPoints')) }} as expected_points
from deduped
