{{ config(materialized='table') }}

-- One row per (season, conference_id).
--
-- Season-scoped because conference membership and even conference existence change year to
-- year — the same reason dim_team is season-scoped. `conference_name` is the short form
-- ("ACC"), which is what stg_teams.conference carries and therefore what joins.

with conferences as (

    select * from {{ ref('stg_conferences') }}

),

team_counts as (

    select season, conference, count(*) as member_team_count
    from {{ ref('stg_teams') }}
    where conference is not null
    group by season, conference

)

select
    {{ surrogate_key(['c.season', 'c.conference_id']) }} as conference_sk,
    c.season,
    c.conference_id,
    c.conference_name,
    c.conference_long_name,
    c.conference_abbreviation,
    c.classification,
    c.member_count_reported,
    -- Counted from the team dimension rather than trusted from the payload. A divergence
    -- between the two is a realignment the team list has and the conference list has not.
    coalesce(t.member_team_count, 0) as member_team_count
from conferences c
left join team_counts t
    on t.season = c.season
   and t.conference = c.conference_name
