-- Matchup: the widest view in the model, one row per game.
--
-- Wide on purpose. This is where a user decides whether to bet, so everything that informs
-- that decision is on one row: both teams' identity and records, the market, the model, the
-- venue, and the head-to-head series. A page that had to join would be a page doing
-- business logic in Streamlit.
--
-- NOT YET PRESENT, and absent rather than faked:
--   weather   fct_game_weather is not built (/games/weather landed, unmodelled)
--   travel    needs venue lat/lon joined to team location; dim_venue has no join key to
--             fct_game, which carries a venue NAME and no usable venue id
--   ratings   fct_team_week_rating is the largest enrichment in the backlog and is primary
--             on zero pages, so it waits
-- Each is a column this view will gain, not a number it will invent in the meantime.
with latest_line as (
    select game_id, spread, over_under, spread_open, over_under_open,
           home_moneyline, away_moneyline, provider_key, snapshot_ts
    from (
        select *, row_number() over (partition by game_id
                                     order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_betting_line') }}
    ) r where recency = 1
),
latest_market as (
    select game_id, market_implied_home_win_probability,
           market_implied_away_win_probability, overround, devig_method
    from (
        select *, row_number() over (partition by game_id
                                     order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_market_probability') }}
    ) r where recency = 1
),
latest_prediction as (
    select game_id, model_name, model_family, predicted_margin, predicted_total_points,
           predicted_home_points, predicted_away_points, predicted_home_win_probability,
           home_cover_edge, home_win_probability_edge, confidence_bucket,
           is_out_of_sample_week
    from (
        select *, row_number() over (partition by game_id
                                     order by prediction_ts desc, model_version desc) as recency
        from {{ ref('fct_prediction') }}
    ) r where recency = 1
),
-- Head-to-head, computed from the game spine rather than a separate endpoint. Counted from
-- the HOME team's perspective in the current game, which is the perspective the page shows.
series as (
    select
        cur.game_id,
        count(*)                                                          as series_games,
        sum(case when prior.home_team_id = cur.home_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.home_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end)                                              as series_home_team_wins,
        min(prior.season)                                                 as series_first_season,
        max(prior.season)                                                 as series_last_season
    from {{ ref('fct_game') }} cur
    join {{ ref('fct_game') }} prior
      on prior.is_completed
     and prior.game_id <> cur.game_id
     and ((prior.home_team_id = cur.home_team_id and prior.away_team_id = cur.away_team_id)
       or (prior.home_team_id = cur.away_team_id and prior.away_team_id = cur.home_team_id))
    group by cur.game_id
)
select
    g.game_sk, g.game_id,
    g.season, g.season_type, g.week, g.week_sk,
    g.start_date, g.game_date, g.kickoff_time_known,
    g.is_completed, g.is_conference_game, g.is_neutral_site, g.venue, g.attendance,

    g.home_team_id, g.home_team, h.abbreviation as home_abbreviation,
    h.conference as home_conference, h.classification as home_classification,
    h.color_on_light as home_color_on_light, h.color_on_dark as home_color_on_dark,
    h.logo_source_url as home_logo_url, g.home_points,
    hr.wins as home_wins, hr.losses as home_losses,

    g.away_team_id, g.away_team, a.abbreviation as away_abbreviation,
    a.conference as away_conference, a.classification as away_classification,
    a.color_on_light as away_color_on_light, a.color_on_dark as away_color_on_dark,
    a.logo_source_url as away_logo_url, g.away_points,
    ar.wins as away_wins, ar.losses as away_losses,

    l.spread, l.spread_open, l.over_under, l.over_under_open,
    l.home_moneyline, l.away_moneyline, l.provider_key, l.snapshot_ts as line_snapshot_ts,
    m.market_implied_home_win_probability, m.market_implied_away_win_probability,
    m.overround, m.devig_method,

    p.model_name, p.model_family,
    p.predicted_margin,
    -1 * p.predicted_margin as predicted_margin_home_perspective,
    p.predicted_total_points, p.predicted_home_points, p.predicted_away_points,
    p.predicted_home_win_probability, p.confidence_bucket,
    p.home_cover_edge, p.home_win_probability_edge,
    p.is_out_of_sample_week,

    s.series_games, s.series_home_team_wins,
    s.series_games - s.series_home_team_wins as series_away_team_wins,
    s.series_first_season, s.series_last_season
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_market m on m.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
left join series s on s.game_id = g.game_id
