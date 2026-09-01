-- Playoff bracket matchups: one row per (season, matchup). The bracket as a graph.
--
-- SLOTS ARE FLATTENED TO POSITION 1 AND 2 RATHER THAN LEFT LONG, which is the opposite call
-- from the box-score models — and the reason is that the key set here is CLOSED. A matchup
-- has exactly two slots, always, and they are ordered; there is no risk of CFBD adding a
-- third the way it can add a stat category. Long would force every caller to self-join to
-- ask "who played whom", which is the only question this table exists to answer.
--
-- `slots[].source` IS NULL WHENEVER THE PARTICIPANT IS KNOWN. Before a round is set it names
-- the feeding matchup instead, so a slot has a participant or a source and not both. Kept
-- because a bracket fetched mid-tournament is a legitimate state and dropping `source` would
-- make those rows look like matchups with a missing team.
--
-- `advancesTo` IS WHAT MAKES IT A BRACKET rather than a list of games — the edge to the next
-- matchup, by id and slot position. Without it the tree cannot be reconstructed.
--
-- TWO GAME IDENTITIES, AND THEY ARE DIFFERENT NUMBERS. `id` is the MATCHUP id inside the
-- bracket (31, 36); `game.id` is the CFBD game id (401677176) that joins to stg_games and
-- everything else. Confusing them joins nothing and raises nothing.

{% set slot_positions = [1, 2] %}

with season_fetches as (

    select
        filename,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_playoffs_cfp_games') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

matchups as (

    select season, {{ json_array_elements('payload') }} as row_json
    from season_fetches
    where recency = 1

)

select
    season,
    -- The matchup id WITHIN the bracket, not the CFBD game id. See the header.
    cast({{ json_get_string('row_json', 'id') }} as int)            as matchup_id,
    {{ json_get_string('row_json', 'bracketSlot') }}                as bracket_slot,
    {{ json_get_string('row_json', 'round') }}                      as round,
    {{ json_get_string('row_json', 'roundName') }}                  as round_name,
    cast({{ json_get_string('row_json', 'roundOrder') }} as int)    as round_order,
    cast({{ json_get_string('row_json', 'matchupOrder') }} as int)  as matchup_order,
    cast({{ json_get_string('row_json', 'startDate') }} as {{ type_timestamp_tz() }})
                                                                    as start_at,
    {{ json_get_string('row_json', 'bowlName') }}                   as bowl_name,

{%- for position in slot_positions %}
    {%- set slot = json_array_element_object(json_get_object('row_json', 'slots'), position - 1) %}
    cast({{ json_get_string(slot, 'seed') }} as int)      as slot_{{ position }}_seed,
    cast({{ json_get_nested_string(slot, ['participant', 'id']) }} as int)
                                                          as slot_{{ position }}_team_id,
    {{ json_get_nested_string(slot, ['participant', 'school']) }}
                                                          as slot_{{ position }}_school,
    {{ json_get_nested_string(slot, ['participant', 'conference']) }}
                                                          as slot_{{ position }}_conference,
    -- `source` is populated only while the participant is unknown, naming the feeding
    -- matchup instead. UNNESTED RATHER THAN CARRIED AS JSON: a slot's source is three
    -- scalars — which matchup, which bracket slot, and whether the winner or loser advances
    -- — and leaving them inside an opaque column is the same "landed but unusable" shape
    -- this whole effort exists to remove.
    cast({{ json_get_nested_string(slot, ['source', 'matchupId']) }} as int)
                                                          as slot_{{ position }}_source_matchup_id,
    {{ json_get_nested_string(slot, ['source', 'bracketSlot']) }}
                                                          as slot_{{ position }}_source_bracket_slot,
    {{ json_get_nested_string(slot, ['source', 'outcome']) }}
                                                          as slot_{{ position }}_source_outcome,
{%- endfor %}

    -- The CFBD game id, which is what joins to stg_games. A different number from matchup_id.
    cast({{ json_get_nested_string('row_json', ['game', 'id']) }} as bigint) as game_id,
    cast({{ json_get_nested_string('row_json', ['game', 'completed']) }} as boolean)
                                                                             as game_completed,
    cast({{ json_get_nested_string('row_json', ['game', 'homeTeam', 'id']) }} as int)
                                                                             as home_team_id,
    {{ json_get_nested_string('row_json', ['game', 'homeTeam', 'school']) }} as home_school,
    {{ json_get_nested_string('row_json', ['game', 'homeTeam', 'conference']) }}
                                                                             as home_conference,
    cast({{ json_get_nested_string('row_json', ['game', 'homePoints']) }} as int)
                                                                             as home_points,
    cast({{ json_get_nested_string('row_json', ['game', 'awayTeam', 'id']) }} as int)
                                                                             as away_team_id,
    {{ json_get_nested_string('row_json', ['game', 'awayTeam', 'school']) }} as away_school,
    {{ json_get_nested_string('row_json', ['game', 'awayTeam', 'conference']) }}
                                                                             as away_conference,
    cast({{ json_get_nested_string('row_json', ['game', 'awayPoints']) }} as int)
                                                                             as away_points,
    cast({{ json_get_nested_string('row_json', ['game', 'venueId']) }} as int) as venue_id,
    {{ json_get_nested_string('row_json', ['game', 'venue']) }}                as venue,

    -- The bracket edge: which matchup the winner feeds, and into which slot.
    cast({{ json_get_nested_string('row_json', ['advancesTo', 'matchupId']) }} as int)
                                                                    as advances_to_matchup_id,
    {{ json_get_nested_string('row_json', ['advancesTo', 'bracketSlot']) }}
                                                                    as advances_to_bracket_slot,
    cast({{ json_get_nested_string('row_json', ['advancesTo', 'position']) }} as int)
                                                                    as advances_to_position
from matchups
