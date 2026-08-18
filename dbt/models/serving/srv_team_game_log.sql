-- Team game log: one row per (game, team). Replaces mart_team_schedule.
--
-- Mirrors the mart's columns and semantics exactly so the parity test can compare directly.
-- Box-score columns and team identity are additive and excluded from parity.

select
    g.game_team_sk,
    cast(g.season as {{ dbt.type_string() }}) || '-' || cast(g.game_id as {{ dbt.type_string() }})
        || '-' || cast(g.team_id as {{ dbt.type_string() }}) as team_game_key,
    g.season,
    g.week,
    g.season_type,
    g.game_id,
    g.team_id,
    g.team,
    t.conference,
    coalesce(t.classification, g.classification) as classification,
    g.opponent_team_id as opponent_id,
    g.opponent,
    o.conference as opponent_conference,
    coalesce(o.classification, g.opponent_classification) as opponent_classification,
    f.start_date,
    g.game_date,
    g.kickoff_time_known,
    case when g.is_neutral_site then 'neutral' when not g.is_home then 'away' else 'home' end as venue_role,
    g.is_conference_game,
    g.is_neutral_site,
    g.venue,
    g.attendance,
    g.is_completed,
    g.points_for,
    g.points_against,
    g.result,
    g.margin,
    -- Additive beyond the mart.
    g.first_downs, g.total_yards, g.rushing_yards, g.passing_yards,
    g.turnovers, g.third_down_conversions, g.third_down_attempts, g.possession_seconds,
    g.has_box_score,
    t.color_on_light, t.color_on_dark, t.logo_source_url
from {{ ref('fct_game_team') }} g
join {{ ref('fct_game') }} f on f.game_id = g.game_id
left join {{ ref('dim_team') }} t on t.season = g.season and t.team_id = g.team_id
left join {{ ref('dim_team') }} o on o.season = g.season and o.team_id = g.opponent_team_id
