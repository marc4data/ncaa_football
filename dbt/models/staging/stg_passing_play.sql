-- Enriched pass attempts: one row per pass. The most detailed play data in the project.
--
-- Where stg_play describes every play with a text string, this describes every PASS with
-- structured geometry — where it was thrown, how far in the air, who it was aimed at, and
-- what happened. 7,396 rows for a single week, which is why the endpoint is week-scoped and
-- opt-in.
--
-- `parseStatus` IS A QUALITY FLAG AND MUST NOT BE IGNORED, AND IT IS NOT A RARE CASE.
-- Measured on the landed data: 29,750 rows are `partial` against 24,322 `complete` — the
-- MAJORITY of pass plays are only partially parsed.
--
-- These fields are derived by parsing the play text, and a row whose geometry is null because
-- the parse failed looks identical to one where the throw genuinely had no air yards. Only
-- this column separates them, and at 55% partial the distinction is not an edge case: any
-- analysis that ignores it is silently mixing "unknown" with "zero" on most of its rows.
--
-- Carried verbatim, and nothing here filters on it — that is a mart's decision, made visibly.
--
-- THREE IDS THAT ALL JOIN SOMEWHERE. `playId` to stg_play, `driveId` to stg_drive, `gameId`
-- to stg_games — so a pass can be placed in its drive and its game without a name match.
-- `passerId` and `targetId` are athlete ids, which /games/players does not carry.
--
-- `isSpike`, `isThrowaway` and `isIntentionalGrounding` mark passes that were never intended
-- to be caught. Any completion-rate computed off this table without excluding them is
-- measuring something other than passing accuracy.

{% set geometry = ['airYards', 'passDepth', 'totalYards', 'yardsAfterCatch',
                   'startYardline', 'startYardsToGoal', 'targetYardsToGoal'] %}
{% set flags = ['isSpike', 'isThrowaway', 'isIntentionalGrounding'] %}

with successful_fetches as (

    select
        filename,
        {{ json_get_object('content', 'data') }} as payload
    from {{ source('raw', 'raw_passing_plays') }}
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
                partition by {{ json_get_string('row_json', 'playId') }}
                order by filename desc
            ) as recency
        from exploded
    ) ranked
    where recency = 1

)

select
    {{ json_get_string('row_json', 'playId') }}                 as play_id,
    {{ json_get_string('row_json', 'driveId') }}                as drive_id,
    cast({{ json_get_string('row_json', 'gameId') }} as bigint) as game_id,
    cast({{ json_get_string('row_json', 'season') }} as int)    as season,
    cast({{ json_get_string('row_json', 'week') }} as int)      as week,
    {{ json_get_string('row_json', 'seasonType') }}             as season_type,

    cast({{ json_get_string('row_json', 'offenseId') }} as int) as offense_team_id,
    {{ json_get_string('row_json', 'offense') }}                as offense,
    {{ json_get_string('row_json', 'offenseConference') }}      as offense_conference,
    cast({{ json_get_string('row_json', 'defenseId') }} as int) as defense_team_id,
    {{ json_get_string('row_json', 'defense') }}                as defense,
    {{ json_get_string('row_json', 'defenseConference') }}      as defense_conference,

    cast({{ json_get_string('row_json', 'period') }} as int)    as period,
    cast({{ json_get_nested_string('row_json', ['clock', 'minutes']) }} as int)
                                                                as clock_minutes,
    cast({{ json_get_nested_string('row_json', ['clock', 'seconds']) }} as int)
                                                                as clock_seconds_part,
    cast({{ json_get_string('row_json', 'down') }} as int)      as down,
    cast({{ json_get_string('row_json', 'distance') }} as int)  as distance,

    {{ json_get_string('row_json', 'passerId') }}               as passer_id,
    {{ json_get_string('row_json', 'passer') }}                 as passer,
    -- Null on an incompletion with no identifiable target, and on a throwaway.
    {{ json_get_string('row_json', 'targetId') }}               as target_id,
    {{ json_get_string('row_json', 'target') }}                 as target,
    {{ json_get_string('row_json', 'outcome') }}                as outcome,
    {{ json_get_string('row_json', 'passDirection') }}          as pass_direction,
    {{ json_get_string('row_json', 'passLocation') }}           as pass_location

{%- for field in geometry %},
    {{ safe_numeric(json_get_string('row_json', field)) }} as {{ snake_case(field) }}
{%- endfor %}
{%- for flag in flags %},
    cast({{ json_get_string('row_json', flag) }} as boolean) as {{ snake_case(flag) }}
{%- endfor %},

    -- The quality flag. See the header: it is the only thing separating "no air yards" from
    -- "the parse could not tell".
    {{ json_get_string('row_json', 'parseStatus') }}            as parse_status,
    {{ json_get_string('row_json', 'playText') }}               as play_text
from deduped
