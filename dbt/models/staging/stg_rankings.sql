-- CFBD /rankings, flattened from week -> poll -> rank into one row per ranked team.
--
-- Three levels of nesting collapse here. The response is a list of weeks, each carrying a
-- list of polls, each carrying a list of ranks — so a single file can hold several hundred
-- rows and the same team appears once per poll it is ranked in.
--
-- Latest-file-per-params, like the other season-scoped staging models: a re-fetch of the
-- same season supersedes the earlier one rather than duplicating it. Polls are revised in
-- place, so the most recent fetch is the correct one.
with successful_fetches as (
    select
        filename,
        params,
        {{ json_get_object('content', 'data') }} as payload,
        row_number() over (partition by params order by filename desc) as recency
    from {{ source('raw', 'raw_rankings') }}
    where status_code = 200
),
weeks as (
    select filename, {{ json_array_elements('payload') }} as week_row
    from successful_fetches
    where recency = 1
),
polls as (
    select
        filename,
        cast({{ json_get_string('week_row', 'season') }} as int)  as season,
        {{ json_get_string('week_row', 'seasonType') }}           as season_type,
        cast({{ json_get_string('week_row', 'week') }} as int)    as week,
        {{ json_array_elements(json_get_object('week_row', 'polls')) }} as poll_row
    from weeks
),
ranks as (
    select
        filename,
        season,
        season_type,
        week,
        {{ json_get_string('poll_row', 'poll') }} as poll_name,
        cast({{ json_get_string('poll_row', 'isFinal') }} as boolean) as is_final,
        {{ json_array_elements(json_get_object('poll_row', 'ranks')) }} as rank_row
    from polls
),
-- Deduplicated on the natural key. /rankings is fetched once per (year, seasonType), and
-- the two requests return OVERLAPPING week rows — each payload carries its own seasonType
-- per week, so the same logical poll row arrives in both files. Without this the grain is
-- violated for every season fetched both ways: 100 duplicate keys, found by the uniqueness
-- test rather than by reading the payload.
deduped as (
    select *,
        row_number() over (
            partition by season, season_type, week, poll_name,
                         cast({{ json_get_string('rank_row', 'teamId') }} as int)
            order by filename desc
        ) as row_rank
    from ranks
)
select
    season,
    season_type,
    week,
    poll_name,
    is_final,
    -- Nullable in the source: a team can be "receiving votes" with points but no rank.
    {{ safe_int(json_get_string('rank_row', 'rank')) }}            as rank,
    cast({{ json_get_string('rank_row', 'teamId') }} as int)       as team_id,
    {{ json_get_string('rank_row', 'school') }}                    as school,
    {{ json_get_string('rank_row', 'conference') }}                as conference_name,
    {{ safe_int(json_get_string('rank_row', 'firstPlaceVotes')) }} as first_place_votes,
    {{ safe_int(json_get_string('rank_row', 'points')) }}          as points
from deduped
where row_rank = 1
