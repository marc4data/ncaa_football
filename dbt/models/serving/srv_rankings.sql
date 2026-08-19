-- Rankings page, long by poll: one row per poll x season x week x team.
--
-- Long rather than wide because the page's poll tabs are a filter, not a computation —
-- the app selects WHERE poll_name = ... and renders. Wide would force the app to know
-- which columns exist, and the poll list is not stable across eras.
select
    r.poll_rank_sk,
    r.season,
    r.season_type,
    r.week,
    r.poll_name,
    p.division        as poll_division,
    p.is_committee    as poll_is_committee,
    p.display_order   as poll_display_order,
    r.rank,
    r.team_id,
    r.school,
    r.conference_name,
    r.first_place_votes,
    r.points,
    r.is_final,
    r.is_receiving_votes,
    t.color_raw       as color_primary,
    t.color_on_light,
    t.color_on_dark,
    t.logo_path,
    ao_src.as_of_ts,
    t.team_slug,
    t.team_display,
    t.logo_source_url as logo_url,
    t.conference
from {{ ref('fct_poll_rank') }} r
left join {{ ref('dim_poll') }} p on p.poll_sk = r.poll_sk
left join {{ ref('dim_team') }} t on t.season = r.season and t.team_id = r.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'rankings') ao_src
