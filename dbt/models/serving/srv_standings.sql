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
    {{ team_identity('t', 'r.school') }},
    t.logo_source_url as logo_url,

    -- DIVISION, and absence here is NORMAL rather than missing data. AC-5.2 groups by
    -- division "where a conference has them", and post-realignment only 159 of 2,044
    -- FBS team-seasons have one — the SEC and Big Ten dropped divisions in 2024. A page
    -- that renders a Degraded state for the other 92% would be reporting a defect that
    -- does not exist. Null means "this conference does not have divisions", full stop.
    t.division,

    r.conference_win_pct,
    r.home_wins, r.home_losses, r.away_wins, r.away_losses, r.neutral_games,
    -- Pre-formatted strings, per AC-5.3. The app never assembles "5-7" from two columns:
    -- a record is one fact with a conventional rendering, not two numbers and a hyphen
    -- decided in Python.
    r.home_record_display,
    r.away_record_display,
    r.current_streak_display,
    r.current_streak_outcome,
    r.current_streak_length,
    r.last_5_display,
    -- ATS from the fact, sharing one definition with the Team page rather than
    -- recomputing it here. Null, never 0-0-0, where nothing has been graded.
    r.ats_record_display,
    r.ats_as_favorite_display,
    r.ats_as_underdog_display
from {{ ref('fct_team_record') }} r
left join {{ ref('dim_team') }} t
    on t.season = r.season and t.team_id = r.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
