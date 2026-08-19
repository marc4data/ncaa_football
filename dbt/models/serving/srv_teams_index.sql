-- Teams index: one row per (season, team), conference-grouped. Additive.
select
    t.team_sk, t.season, t.team_id, t.school, t.mascot, t.abbreviation,
    t.conference, t.conference_sk, t.classification, t.is_fbs, t.city, t.state,
    t.color_on_light, t.color_on_dark, t.color_source_light, t.color_source_dark,
    t.logo_source_url,
    r.games_played, r.wins, r.losses, r.ties, r.win_pct, r.tiebreak_rank,
    ao_src.as_of_ts
from {{ ref('dim_team') }} t
left join {{ ref('fct_team_record') }} r on r.season = t.season and r.team_id = t.team_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'team') ao_src
