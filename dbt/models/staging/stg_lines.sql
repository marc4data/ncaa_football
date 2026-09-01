-- One row per (game, provider, snapshot). The betting-line spine.
--
-- Unlike every other staging model this one does NOT deduplicate to the latest fetch.
-- Repeated fetches of the same request are the entire point: /lines returns only the
-- opening and current line with nothing in between, so the movement between snapshots
-- exists only because we sampled it, and it cannot be backfilled.
--
-- snapshot_ts comes from raw_manifest.fetched_at — when the line was OBSERVED, not when the
-- file was loaded. Load time would make every snapshot in a catch-up load look simultaneous.

with responses as (

    select
        r.filename,
        m.fetched_at as snapshot_ts,
        {{ json_get_object('r.content', 'data') }} as payload
    from {{ source('raw', 'raw_lines') }} r
    join {{ source('raw', 'raw_manifest') }} m
        on m.endpoint = 'lines' and m.filename = r.filename
    where r.status_code = 200

),

games as (

    select filename, snapshot_ts, {{ json_array_elements('payload') }} as game
    from responses

),

lines_long as (

    select
        filename,
        snapshot_ts,
        cast({{ json_get_string('game', 'id') }} as int)     as game_id,
        cast({{ json_get_string('game', 'season') }} as int) as season,
        cast({{ json_get_string('game', 'week') }} as int)   as week,
        {{ json_get_string('game', 'seasonType') }}          as season_type,
        cast({{ json_get_string('game', 'startDate') }} as {{ type_timestamp_tz() }})
                                                             as start_date,

        -- THE MATCHUP, WHICH THIS MODEL DID NOT CARRY. /lines names both teams, their ids,
        -- conferences, classifications and the score, and the model kept only the game id —
        -- so reading a line meant joining out to stg_games for the two things a line is
        -- about. The ids make that join unnecessary and the classifications make an
        -- FBS-only filter possible without one.
        cast({{ json_get_string('game', 'homeTeamId') }} as int) as home_team_id,
        {{ json_get_string('game', 'homeTeam') }}                as home_team,
        {{ json_get_string('game', 'homeConference') }}          as home_conference,
        {{ json_get_string('game', 'homeClassification') }}      as home_classification,
        -- NULL UNTIL THE GAME IS PLAYED. A snapshot taken before kickoff has no score, which
        -- is most rows in a movement series and is the point of them.
        cast({{ json_get_string('game', 'homeScore') }} as int)  as home_score,
        cast({{ json_get_string('game', 'awayTeamId') }} as int) as away_team_id,
        {{ json_get_string('game', 'awayTeam') }}                as away_team,
        {{ json_get_string('game', 'awayConference') }}          as away_conference,
        {{ json_get_string('game', 'awayClassification') }}      as away_classification,
        cast({{ json_get_string('game', 'awayScore') }} as int)  as away_score,

        {{ json_array_elements(json_get_object('game', 'lines')) }} as line
    from games

)

-- CFBD sometimes emits the SAME book twice in one response under two spellings:
-- "DraftKings" and "Draft Kings" both appear for the same game and snapshot, with identical
-- spread, formatted spread and total, but the "Draft Kings" row carries null moneylines.
-- 56 game-snapshots are affected. They are not two providers, so mapping them to one key
-- creates a genuine grain collision that has to be resolved here rather than downstream.
--
-- Rule: keep the most complete row, tie-broken deterministically by the canonical spelling.
-- assert_provider_dedup_is_lossless proves the discarded row never carries a value the kept
-- row lacks — without that, this would be silent data loss dressed up as deduplication.
select
    filename,
    snapshot_ts,
    game_id,
    season,
    week,
    season_type,
    {{ json_get_string('line', 'provider') }} as provider_raw,
    -- DraftKings is canonical (Marc, 2026-08-17). "Draft Kings" is the same book under a
    -- second spelling and appears in 64 line rows; left unmapped it would split every
    -- provider-level comparison silently.
    case lower(trim({{ json_get_string('line', 'provider') }}))
        when 'draftkings'  then 'draftkings'
        when 'draft kings' then 'draftkings'
        when 'espn bet'    then 'espn_bet'
        when 'bovada'      then 'bovada'
        else null
    end as provider_key,
    start_date,
    home_team_id,
    home_team,
    home_conference,
    home_classification,
    home_score,
    away_team_id,
    away_team,
    away_conference,
    away_classification,
    away_score,
    cast({{ json_get_string('line', 'spread') }} as numeric)         as spread,
    {{ json_get_string('line', 'formattedSpread') }}                 as formatted_spread,
    cast({{ json_get_string('line', 'spreadOpen') }} as numeric)     as spread_open,
    cast({{ json_get_string('line', 'overUnder') }} as numeric)      as over_under,
    cast({{ json_get_string('line', 'overUnderOpen') }} as numeric)  as over_under_open,
    {{ safe_int(json_get_string('line', 'homeMoneyline')) }}         as home_moneyline,
    {{ safe_int(json_get_string('line', 'awayMoneyline')) }}         as away_moneyline,
    row_number() over (
        partition by
            game_id,
            case lower(trim({{ json_get_string('line', 'provider') }}))
                when 'draftkings' then 'draftkings' when 'draft kings' then 'draftkings'
                when 'espn bet' then 'espn_bet' when 'bovada' then 'bovada' else null end,
            snapshot_ts
        order by
            (case when {{ json_get_string('line', 'spread') }} is not null then 1 else 0 end
           + case when {{ json_get_string('line', 'overUnder') }} is not null then 1 else 0 end
           + case when {{ json_get_string('line', 'homeMoneyline') }} is not null then 1 else 0 end
           + case when {{ json_get_string('line', 'awayMoneyline') }} is not null then 1 else 0 end) desc,
            {{ json_get_string('line', 'provider') }} asc
    ) as provider_row_rank
from lines_long
