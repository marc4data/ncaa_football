-- Schedule: ONE ROW PER GAME. Not one per team — the grain inversion the spec once carried
-- backwards, so a count here equals the game count for the filtered scope, never twice it.
with latest_line as (
    select game_id, spread, over_under
    from (
        select b.*, row_number() over (partition by b.game_id
                                       order by b.snapshot_ts desc, b.provider_key) as recency
        from {{ ref('fct_betting_line') }} b
    ) r where recency = 1
),
latest_prediction as (
    -- Prefer a model that populates predicted_margin: six of seven models are probability
    -- models, so ordering by recency alone loses the margin almost every time.
    select game_id, predicted_margin, predicted_home_win_probability, model_name
    from (
        select p.*, row_number() over (
                   partition by p.game_id
                   order by case when p.predicted_margin is not null then 0 else 1 end,
                            p.prediction_ts desc, p.model_version desc) as recency
        from {{ ref('fct_prediction') }} p
    ) r where recency = 1
)
select
    g.game_sk,
    g.game_id,
    g.season,
    g.week,
    g.season_type,
    g.week_sk,
    g.game_date,
    g.start_date,
    -- AC-G.34: the display zone is applied here, never in the app.
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.kickoff_time_known,
    g.is_completed,
    g.is_conference_game,
    g.is_neutral_site,
    g.venue                       as venue_display,
    g.network,
    g.attendance,
    g.excitement_index,

    g.home_team_id,
    {{ team_identity('h', 'g.home_team', 'home_') }},
    h.abbreviation                as home_abbreviation,
    h.conference                  as home_conference,
    h.color_on_light              as home_color_on_light,
    h.color_on_dark               as home_color_on_dark,
    h.logo_source_url             as home_logo_url,
    g.home_points,
    g.home_rank,

    g.away_team_id,
    {{ team_identity('a', 'g.away_team', 'away_') }},
    a.abbreviation                as away_abbreviation,
    a.conference                  as away_conference,
    a.color_on_light              as away_color_on_light,
    a.color_on_dark               as away_color_on_dark,
    a.logo_source_url             as away_logo_url,
    g.away_points,
    g.away_rank,

    l.spread                      as spread_current,
    l.over_under                  as total_current,
    p.predicted_margin,
    -- Home-perspective is a separate, explicitly named column; the pack's away-minus-home
    -- sign is preserved on predicted_margin itself.
    -1 * p.predicted_margin       as predicted_margin_home_perspective,
    p.predicted_home_win_probability as home_win_probability,
    p.model_name                  as model_version_key,

    ao.as_of_ts
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao
