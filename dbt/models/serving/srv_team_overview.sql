-- Team page, Overview tab: one row per team per season.
--
-- BUILT NARROWED, by decision. Identity, record, conference standing and ATS are derivable
-- from facts that exist today. The ratings and profile block — sp_plus, elo, srs, adjusted
-- EPA, success rate, points per drive, havoc, returning production, coach — is NOT here,
-- because every one of those depends on a fact scheduled in Track B.
--
-- The columns are deliberately ABSENT rather than present-and-null. A null column reads as
-- "no data for this team"; an absent column lets the page render its Degraded state and
-- name `fct_team_week_rating`, which is the honest signal and what AC-8.2 asks for.
with ats as (
    -- Against-the-spread record, from the game spine and the closing line. Computed here
    -- because AC-5.3/AC-G.2 forbid the app assembling records from components.
    --
    -- Sign convention, stated because it governs the whole calculation: margin is
    -- away - home, and the home side covers when margin < spread.
    select
        t.season,
        t.team_id,
        sum(case when t.covered then 1 else 0 end)                      as ats_wins,
        sum(case when t.covered is false then 1 else 0 end)             as ats_losses,
        sum(case when t.covered is null and t.spread is not null then 1 else 0 end) as ats_pushes,
        sum(case when t.is_favorite and t.covered then 1 else 0 end)    as ats_fav_wins,
        sum(case when t.is_favorite and t.covered is false then 1 else 0 end) as ats_fav_losses,
        sum(case when not t.is_favorite and t.covered then 1 else 0 end) as ats_dog_wins,
        sum(case when not t.is_favorite and t.covered is false then 1 else 0 end) as ats_dog_losses
    from (
        select
            g.season,
            g.home_team_id as team_id,
            l.spread,
            l.spread < 0   as is_favorite,
            case when g.away_points - g.home_points < l.spread then true
                 when g.away_points - g.home_points > l.spread then false end as covered
        from {{ ref('fct_game') }} g
        join (
            select game_id, spread from (
                select b.*, row_number() over (partition by b.game_id
                                               order by b.snapshot_ts desc, b.provider_key) as r
                from {{ ref('fct_betting_line') }} b
            ) x where r = 1
        ) l on l.game_id = g.game_id
        where g.is_completed and l.spread is not null

        union all

        select
            g.season,
            g.away_team_id as team_id,
            -1 * l.spread,
            l.spread > 0,
            case when g.away_points - g.home_points > l.spread then true
                 when g.away_points - g.home_points < l.spread then false end
        from {{ ref('fct_game') }} g
        join (
            select game_id, spread from (
                select b.*, row_number() over (partition by b.game_id
                                               order by b.snapshot_ts desc, b.provider_key) as r
                from {{ ref('fct_betting_line') }} b
            ) x where r = 1
        ) l on l.game_id = g.game_id
        where g.is_completed and l.spread is not null
    ) t
    group by t.season, t.team_id
)
select
    {{ surrogate_key(['d.season', 'd.team_id']) }} as team_overview_sk,
    d.season,
    d.team_id,
    d.team_slug,
    d.team_display,
    d.mascot,
    d.abbreviation,
    d.logo_source_url        as logo_url,
    d.color_raw              as color_primary,
    d.color_on_light,
    d.color_on_dark,
    d.color_source,
    d.conference,
    d.division,
    d.classification,
    d.city, d.state,

    r.wins, r.losses,
    -- Pre-formatted, per AC-5.3: the app must not assemble a record from components.
    cast(r.wins as {{ dbt.type_string() }}) || '-' || cast(r.losses as {{ dbt.type_string() }})
        as record_display,
    s.tiebreak_rank          as conference_standing,
    s.conference_wins, s.conference_losses,
    cast(s.conference_wins as {{ dbt.type_string() }}) || '-'
        || cast(s.conference_losses as {{ dbt.type_string() }}) as conference_record_display,

    coalesce(a.ats_wins, 0) as ats_wins,
    coalesce(a.ats_losses, 0) as ats_losses,
    coalesce(a.ats_pushes, 0) as ats_pushes,
    cast(coalesce(a.ats_wins,0) as {{ dbt.type_string() }}) || '-'
        || cast(coalesce(a.ats_losses,0) as {{ dbt.type_string() }}) || '-'
        || cast(coalesce(a.ats_pushes,0) as {{ dbt.type_string() }}) as ats_record_display,
    cast(coalesce(a.ats_fav_wins,0) as {{ dbt.type_string() }}) || '-'
        || cast(coalesce(a.ats_fav_losses,0) as {{ dbt.type_string() }}) as ats_as_favorite_display,
    cast(coalesce(a.ats_dog_wins,0) as {{ dbt.type_string() }}) || '-'
        || cast(coalesce(a.ats_dog_losses,0) as {{ dbt.type_string() }}) as ats_as_underdog_display,

    ao.as_of_ts
from {{ ref('dim_team') }} d
left join {{ ref('fct_team_record') }} r on r.season = d.season and r.team_id = d.team_id
left join {{ ref('srv_standings') }} s on s.season = d.season and s.team_id = d.team_id
left join ats a on a.season = d.season and a.team_id = d.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
