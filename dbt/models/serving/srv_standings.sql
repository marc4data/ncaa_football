-- Standings: one row per (season, team). Replaces mart_team_season_record.
--
-- Denormalized on purpose — the site reads exactly one of these per view, with a WHERE
-- clause and no joins. Column names and semantics deliberately mirror the mart it replaces
-- so the parity test can compare them directly; new columns (tiebreak_rank, colours) are
-- additive and excluded from parity.

select
    r.team_season_sk,
    -- Retained under the mart's original name so the parity test compares like with like.
    cast(r.season as {{ dbt.type_string() }}) || '-' || cast(r.team_id as {{ dbt.type_string() }}) as team_season_key,
    r.season,
    r.team_id,
    r.is_listed_team,
    r.school,
    r.conference,
    r.classification,
    r.games_played,
    r.wins,
    r.losses,
    r.ties,
    r.points_for,
    r.points_against,
    r.point_differential,
    r.win_pct,
    -- Additive beyond the mart.
    r.conference_wins,
    r.conference_losses,
    r.tiebreak_rank,
    r.tiebreak_basis,
    t.color_on_light,
    t.color_on_dark,
    t.logo_source_url,
    t.abbreviation,
    ao_src.as_of_ts,
    t.team_slug,
    t.team_display
from {{ ref('fct_team_record') }} r
left join {{ ref('dim_team') }} t
    on t.season = r.season and t.team_id = r.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
