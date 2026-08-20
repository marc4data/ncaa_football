-- Today page: the current slate, with market and model side by side.
--
-- One row per game in the week currently in play. Deliberately narrower than the Edge
-- Finder — this page answers "what is on today and where does the model disagree", not
-- "let me filter every market by edge size".
--
-- "Today" is the current CFBD week rather than a calendar date, because a slate spans
-- Thursday to Saturday and a date filter would show an empty page on Wednesday.
-- The upcoming week: the earliest week holding a game that has not started yet.
--
-- `not is_completed` alone is NOT sufficient, and picking it selected 2023 week 6 on the
-- first build. Twelve historical games (10 in 2023, 2 in 2024) are permanently flagged
-- incomplete — cancelled or abandoned, and CFBD never marks them otherwise — so the
-- earliest incomplete game is three seasons in the past. Anchoring on kickoff time rather
-- than completion makes those rows irrelevant instead of authoritative.
with current_week as (
    select season, season_type, week
    from {{ ref('fct_game') }}
    where start_date >= {{ dbt.current_timestamp() }}
    group by season, season_type, week
    order by min(start_date)
    limit 1
),
latest_line as (
    select game_id, spread, over_under, home_moneyline, away_moneyline, provider_key, snapshot_ts
    from (
        select *, row_number() over (partition by game_id
                                     order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_betting_line') }}
    ) r where recency = 1
),
latest_market as (
    select game_id, market_implied_home_win_probability, devig_method
    from (
        select *, row_number() over (partition by game_id
                                     order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_market_probability') }}
    ) r where recency = 1
),
latest_prediction as (
    select game_id, model_name, model_version, predicted_margin, predicted_home_win_probability,
           predicted_home_points, predicted_away_points, home_cover_edge,
           home_win_probability_edge, confidence_bucket, is_out_of_sample_week
    from (
        select *, row_number() over (partition by game_id
                                     order by case when predicted_margin is not null then 0 else 1 end,
                                                prediction_ts desc, model_version desc) as recency
        from {{ ref('fct_prediction') }}
    ) r where recency = 1
)
select
    g.game_sk,
    g.game_id,
    g.season, g.season_type, g.week,
    g.start_date, g.kickoff_time_known, g.is_neutral_site, g.venue,
    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation,
    h.color_on_light as home_color_on_light, h.logo_source_url as home_logo_url,
    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation,
    a.color_on_light as away_color_on_light, a.logo_source_url as away_logo_url,
    -- Market
    l.spread, l.over_under, l.home_moneyline, l.away_moneyline, l.provider_key,
    m.market_implied_home_win_probability, m.devig_method,
    -- Model. predicted_margin keeps the pack's away-minus-home sign; the home-perspective
    -- value is separate and explicitly named.
    p.model_name, p.predicted_margin,
    -1 * p.predicted_margin as predicted_margin_home_perspective,
    p.predicted_home_win_probability, p.predicted_home_points, p.predicted_away_points,
    p.confidence_bucket,
    -- Edge, derived once in fct_prediction and only consumed here.
    p.home_cover_edge, p.home_win_probability_edge,
    p.is_out_of_sample_week,
    case when p.is_out_of_sample_week then false else true end as is_default_actionable,
    ao_src.as_of_ts,
    mv_src.model_version as model_version_key,
    mv_src.attribution,
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    {{ team_identity('h', 'g.home_team', 'home_') }},
    {{ team_identity('a', 'g.away_team', 'away_') }},
    h.color_on_dark as home_color_on_dark,
    g.venue as venue_display,
    g.network,
    l.spread as spread_current,
    l.over_under as total_current,
    p.predicted_home_win_probability as home_win_probability,
    g.excitement_index,
    -- The model's own coverage floor, carried as DATA so the Empty state is not a
    -- hardcoded "Week 5" string. CFBD does not ship current-season feature files until
    -- week 5, because the models need several weeks of this year's results before they can
    -- forecast this year's teams. Weeks 1-4 having no predictions is BY DESIGN and recurs
    -- every season — which makes it EMPTY (the data does not exist yet, and here is why),
    -- never Degraded (we have not built it).
    {{ var('prediction_training_week_floor', 5) }} as training_week_floor
from {{ ref('fct_game') }} g
join current_week w
  on w.season = g.season and w.season_type = g.season_type and w.week = g.week
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_market m on m.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
-- AC-G.41: the licence-required attribution travels as DATA, so a page physically
-- cannot draw the model's numbers without it.
left join {{ ref('dim_model_version') }} mv_src
    on mv_src.model_name = p.model_name
   and mv_src.model_version = p.model_version
