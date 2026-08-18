{{ config(materialized='table') }}

-- One row per (season, team). Derived from the game spine, not from /records.
--
-- CFBD has no standings endpoint. /records exists and is landed, but it is used as a
-- RECONCILIATION TEST against this derivation rather than as the source — two independent
-- derivations that must agree is a stronger data-quality artifact than trusting one.
--
-- tiebreak_rank is cfdb's own ordering logic, and the page must be able to say so.
-- tiebreak_basis names the rule applied so the UI can label it rather than implying an
-- official standing.

with team_games as (

    select *
    from {{ ref('fct_game_team') }}
    where is_completed
      and points_for is not null
      and points_against is not null

),

aggregated as (

    select
        season,
        team_sk,
        team_id,
        count(*)                                                   as games_played,
        count(case when points_for > points_against then 1 end)    as wins,
        count(case when points_for < points_against then 1 end)    as losses,
        count(case when points_for = points_against then 1 end)    as ties,
        count(case when is_conference_game and points_for > points_against then 1 end) as conference_wins,
        count(case when is_conference_game and points_for < points_against then 1 end) as conference_losses,
        sum(points_for)                                            as points_for,
        sum(points_against)                                        as points_against
    from team_games
    group by season, team_sk, team_id

),

with_team as (

    select
        a.*,
        t.school,
        t.conference,
        t.conference_sk,
        t.classification,
        t.team_sk is not null as is_listed_team
    from aggregated a
    left join {{ ref('dim_team') }} t
        on t.season = a.season and t.team_id = a.team_id

)

select
    {{ surrogate_key(['w.season', 'w.team_id']) }} as team_season_sk,
    w.season,
    w.team_sk,
    w.team_id,
    w.school,
    w.conference,
    w.conference_sk,
    w.classification,
    w.is_listed_team,
    w.games_played,
    w.wins,
    w.losses,
    w.ties,
    w.conference_wins,
    w.conference_losses,
    w.points_for,
    w.points_against,
    w.points_for - w.points_against as point_differential,
    round(cast(w.wins as numeric) / nullif(w.games_played, 0), 3) as win_pct,
    -- Ordering within (season, conference). Real conference tiebreakers involve
    -- head-to-head and are conference-specific; this is the simple rule, labelled as such.
    case when w.conference is null then null else
        row_number() over (
            partition by w.season, w.conference
            order by
                cast(w.conference_wins as numeric)
                    / nullif(w.conference_wins + w.conference_losses, 0) desc nulls last,
                cast(w.wins as numeric) / nullif(w.games_played, 0) desc nulls last,
                (w.points_for - w.points_against) desc,
                w.school
        )
    end as tiebreak_rank,
    case when w.conference is null then null
         else 'conference_win_pct,overall_win_pct,point_differential,school_name'
    end as tiebreak_basis
from with_team w
