-- Teams index: one row per (season, team), conference-grouped. Additive.
select
    t.team_sk, t.season, t.team_id, t.school, t.mascot, t.abbreviation,
    t.conference, t.conference_sk, t.classification, t.is_fbs, t.city, t.state,
    t.color_on_light, t.color_on_dark, t.color_source_light, t.color_source_dark,
    t.logo_source_url,
    r.games_played, r.wins, r.losses, r.ties, r.win_pct, r.tiebreak_rank
from {{ ref('dim_team') }} t
left join {{ ref('fct_team_record') }} r on r.season = t.season and r.team_id = t.team_id
