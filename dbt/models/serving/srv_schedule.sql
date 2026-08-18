-- Schedule: one row per game, both teams resolved. Additive — replaces no mart.
select
    g.game_sk, g.game_id, g.season, g.week, g.season_type, g.week_sk,
    g.game_date, g.start_date, g.kickoff_time_known,
    g.is_completed, g.is_conference_game, g.is_neutral_site, g.venue, g.attendance,
    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation, h.conference as home_conference,
    h.color_on_light as home_color_on_light, h.color_on_dark as home_color_on_dark,
    h.logo_source_url as home_logo_url, g.home_points,
    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation, a.conference as away_conference,
    a.color_on_light as away_color_on_light, a.color_on_dark as away_color_on_dark,
    a.logo_source_url as away_logo_url, g.away_points
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
