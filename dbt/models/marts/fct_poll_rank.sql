{{ config(materialized='table', tags=['rankings']) }}
-- One row per poll x season x week x ranked team. Periodic snapshot: each week's poll is a
-- fresh observation, and earlier weeks are never revised.
--
-- Teams "receiving votes" carry points with a null rank. They are kept, because the
-- Rankings page shows them below the ranked list and dropping them would make points
-- totals disagree with the published poll.
select
    {{ surrogate_key(['r.poll_name', 'r.season', 'r.season_type', 'r.week', 'r.team_id']) }}
        as poll_rank_sk,
    p.poll_sk,
    r.poll_name,
    r.season,
    r.season_type,
    r.week,
    {{ surrogate_key(['r.season', 'r.season_type', 'r.week']) }} as week_sk,
    r.team_id,
    {{ surrogate_key(['r.season', 'r.team_id']) }} as team_sk,
    r.school,
    r.conference_name,
    r.rank,
    r.first_place_votes,
    r.points,
    r.is_final,
    r.rank is null as is_receiving_votes
from {{ ref('stg_rankings') }} r
left join {{ ref('dim_poll') }} p on p.poll_name = r.poll_name
