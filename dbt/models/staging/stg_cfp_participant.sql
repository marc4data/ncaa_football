-- Playoff field: one row per (season, team). Who got in, how, and how far they went.
--
-- SEASON COMES FROM THE REQUEST. The rows carry no year — /playoffs/cfp/participants is
-- fetched per season and the payload assumes you know which — so unparameterized fetches are
-- excluded and the season is read from `params`.
--
-- `bidType` AND `conferenceChampion` ARE NOT THE SAME QUESTION. A team can be a conference
-- champion without an automatic bid, and the twelve-team format grants automatic bids to the
-- five highest-ranked champions only. Both are carried because the difference is exactly what
-- makes a bracket argument.
--
-- `eliminatedRound` IS NULL FOR THE CHAMPION — they were never eliminated — and `outcome`
-- carries the same fact positively. A count of eliminations that ignores the null undercounts
-- the field by one.

with season_fetches as (

    select
        filename,
        cast({{ json_get_string('params', 'year') }} as int) as season,
        {{ json_get_object('content', 'data') }}             as payload,
        row_number() over (
            partition by {{ json_get_string('params', 'year') }}
            order by filename desc
        ) as recency
    from {{ source('raw', 'raw_playoffs_cfp_participants') }}
    where status_code = 200
      and {{ json_get_string('params', 'year') }} is not null

),

participants as (

    select season, {{ json_array_elements('payload') }} as row_json
    from season_fetches
    where recency = 1

)

select
    season,
    cast({{ json_get_nested_string('row_json', ['team', 'id']) }} as int) as team_id,
    {{ json_get_nested_string('row_json', ['team', 'school']) }}          as school,
    {{ json_get_nested_string('row_json', ['team', 'conference']) }}      as conference,
    cast({{ json_get_string('row_json', 'committeeRank') }} as int)       as committee_rank,
    cast({{ json_get_string('row_json', 'seed') }} as int)                as seed,
    {{ json_get_string('row_json', 'bidType') }}                          as bid_type,
    {{ json_get_string('row_json', 'qualificationReason') }}              as qualification_reason,
    cast({{ json_get_string('row_json', 'conferenceChampion') }} as boolean)
                                                                          as conference_champion,
    {{ json_get_string('row_json', 'qualifyingConference') }}             as qualifying_conference,
    cast({{ json_get_string('row_json', 'firstRoundBye') }} as boolean)   as first_round_bye,
    {{ json_get_string('row_json', 'outcome') }}                          as outcome,
    -- Null for the champion. See the header.
    {{ json_get_string('row_json', 'eliminatedRound') }}                  as eliminated_round
from participants
