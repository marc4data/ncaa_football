-- Drives: one row per drive. The layer between a game and its plays.
--
-- START AND END ARE SYMMETRIC, plus an elapsed block, and all three carry the same clock
-- object as stg_play. Generated from one list so `end_yardline` reading `start.yardline` is
-- unrepresentable.
--
-- `startYardsToGoal` AND `startYardline` ARE DIFFERENT MEASUREMENTS OF THE SAME SPOT, from
-- opposite ends of the field. Both are kept because which one is "the" field position depends
-- entirely on whose drive it is, and collapsing them would bake in an assumption.
--
-- `isHomeOffense` IS THE ONLY LINK TO HOME AND AWAY on this payload — the drive names its
-- offense and defense by school, never as home or away. Without it, matching a drive to a
-- game's home team means a name comparison.
--
-- `id` IS A STRING and joins to stg_play.drive_id, which is also a string. Both left as text
-- for the same reason: eighteen-digit identifiers CFBD never promised are numeric.

{% set clock_parts = ['minutes', 'seconds'] %}

{#- WIRE KEYS SPELLED IN FULL RATHER THAN BUILT BY CONCATENATION.
    `prefix ~ 'Period'` reads fine and produces the right SQL, but it means the string
    `startPeriod` never appears anywhere in this file — and the coverage matrix, which reads
    the field names a model mentions, then reported /drives as 14 of 24 while the model
    exposed all of them. Writing the keys out keeps the start/end pairing visible AND keeps
    the model honest about what it reads. #}
{% set position_blocks = {
    'start': ['startPeriod', 'startYardline', 'startYardsToGoal',
              'startOffenseScore', 'startDefenseScore'],
    'end':   ['endPeriod', 'endYardline', 'endYardsToGoal',
              'endOffenseScore', 'endDefenseScore'],
} %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_drives') }}
    where status_code = 200

),

exploded as (

    select filename, {{ json_array_elements('payload') }} as drive
    from successful_fetches

),

deduped as (

    select drive
    from (
        select
            drive,
            row_number() over (
                partition by {{ json_get_string('drive', 'id') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('drive', 'id') }}                        as drive_id,
    cast({{ json_get_string('drive', 'gameId') }} as bigint)    as game_id,
    cast({{ json_get_string('drive', 'driveNumber') }} as int)  as drive_number,

    {{ json_get_string('drive', 'offense') }}                   as offense,
    {{ json_get_string('drive', 'offenseConference') }}         as offense_conference,
    {{ json_get_string('drive', 'defense') }}                   as defense,
    {{ json_get_string('drive', 'defenseConference') }}         as defense_conference,
    -- The only link to home/away on this payload. See the header.
    cast({{ json_get_string('drive', 'isHomeOffense') }} as boolean) as is_home_offense,

    cast({{ json_get_string('drive', 'scoring') }} as boolean)  as is_scoring_drive,
    cast({{ json_get_string('drive', 'plays') }} as int)        as plays,
    cast({{ json_get_string('drive', 'yards') }} as int)        as yards,
    {{ json_get_string('drive', 'driveResult') }}               as drive_result

{%- for prefix, keys in position_blocks.items() %}
    {%- for key in keys %},
    cast({{ json_get_string('drive', key) }} as int) as {{ snake_case(key) }}
    {%- endfor %}
    {%- for part in clock_parts %},
    cast({{ json_get_nested_string('drive', [prefix ~ 'Time', part]) }} as int)
        as {{ prefix }}_clock_{{ part }}
    {%- endfor %}
{%- endfor %}

{%- for part in clock_parts %},
    cast({{ json_get_nested_string('drive', ['elapsed', part]) }} as int)
        {#- `seconds` is the COMPONENT of mm:ss, not the total. Suffixed `_part` so it does
            not collide with the derived total below — which it did, and Postgres caught it
            as "column elapsed_seconds specified more than once". Same convention as
            stg_play.clock_seconds_part. #}
        as elapsed_{{ part }}{% if part == 'seconds' %}_part{% endif %}
{%- endfor %},
    -- Derived, for the same reason stg_play carries clock_seconds: 2:10 and 12:50 do not
    -- order as text.
    cast({{ json_get_nested_string('drive', ['elapsed', 'minutes']) }} as int) * 60
        + cast({{ json_get_nested_string('drive', ['elapsed', 'seconds']) }} as int)
                                                                    as elapsed_seconds
from deduped
