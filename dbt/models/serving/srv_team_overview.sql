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
--
-- ATS COMES FROM fct_team_record, not from a CTE here.
--
-- It used to be computed in this file, which meant Standings would have needed the same
-- calculation a second time — and two derivations of one definition is the defect this
-- project keeps finding. The record is a business definition and lives in the fact; every
-- view that shows it reads the same columns.
--
-- Moving it also carried the null-not-zero fix: a team that was never a favourite now has
-- NULL as its favourite record rather than "0-0", which claimed a record it never had.
-- 34 team-seasons changed, all of them 0-0 becoming absent.
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

    -- NOT coalesced to zero. A team with no graded games has no ATS record, and `0-0-0`
    -- claims it went 0-0-0 — which is a measurement, not an absence.
    --
    -- The coalesce made every 2026 team read 0-0-0 while wins, losses and record_display in
    -- the SAME ROW were correctly null: one table, two treatments of "hasn't happened yet".
    -- Null lets the page render an em dash per AC-G.32, which is the honest rendering.
    r.games_played,
    r.points_for,
    r.points_against,
    r.point_differential,
    r.yards_for,
    r.rushing_yards_for,
    r.passing_yards_for,
    r.yards_allowed,
    r.rushing_yards_allowed,
    r.passing_yards_allowed,
    r.penalty_yards,
    r.takeaways,
    r.giveaways,
    r.turnover_margin,
    -- AC-G.33: the n every total above was computed over, so a page cannot render a
    -- per-game figure against the wrong denominator.
    r.games_with_box_score,
    r.games_with_opponent_box_score,
    r.ats_wins,
    r.ats_losses,
    r.ats_pushes,
    r.ats_record_display,
    r.ats_as_favorite_display,
    r.ats_as_underdog_display,

    ao.as_of_ts
from {{ ref('dim_team') }} d
left join {{ ref('fct_team_record') }} r on r.season = d.season and r.team_id = d.team_id
left join {{ ref('srv_standings') }} s on s.season = d.season and s.team_id = d.team_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
