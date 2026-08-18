-- Scoreboard: one row per game, carrying both card states. Additive.
-- Pre-game fields and post-game fields live on the same row so the app switches on
-- is_completed rather than querying two objects.
select
    g.game_sk, g.game_id, g.season, g.week, g.season_type, g.game_date, g.start_date,
    g.is_completed, g.is_neutral_site, g.venue,
    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation,
    h.color_on_light as home_color_on_light, h.logo_source_url as home_logo_url,
    g.home_points,
    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation,
    a.color_on_light as away_color_on_light, a.logo_source_url as away_logo_url,
    g.away_points,
    case
        when not g.is_completed then null
        when g.home_points > g.away_points then g.home_team
        when g.away_points > g.home_points then g.away_team
        else null
    end as winner,
    abs(coalesce(g.home_points, 0) - coalesce(g.away_points, 0)) as final_margin,
    hr.wins as home_wins, hr.losses as home_losses,
    ar.wins as away_wins, ar.losses as away_losses
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
