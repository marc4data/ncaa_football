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
    select game_id, model_name, model_version, model_family, predicted_margin, predicted_total_points,
           predicted_home_points, predicted_away_points, predicted_home_win_probability,
           home_cover_edge, home_win_probability_edge, confidence_bucket,
           is_out_of_sample_week
    from (
        select *, row_number() over (partition by game_id
                                     order by case when predicted_margin is not null then 0 else 1 end,
                                                prediction_ts desc, model_version desc) as recency
        from {{ ref('fct_prediction') }}
    ) r where recency = 1
),
-- Head-to-head, computed from the game spine rather than a separate endpoint. Counted from
-- the HOME team's perspective in the current game, which is the perspective the page shows.
series as (
    -- Head-to-head, from the game spine.
    --
    -- Written as a UNION of two equality joins rather than one join with an OR across both
    -- team-pair orderings. The OR form is the obvious way to express it and is a trap:
    -- Postgres cannot hash-join a disjunction, so it degrades to a nested loop over 110,634
    -- games against itself. That built acceptably until fct_game gained four columns, then
    -- ran past 11 minutes without finishing. Same result, and it hash-joins.
    --
    -- A TIE IS ITS OWN OUTCOME and is counted as one. The first version derived the away
    -- record as `series_games - series_home_team_wins`, which is only correct in a sport
    -- without draws: every tie was silently credited to the away team. College football
    -- had no overtime before 1996 and there are 2,600 tied games on record, which
    -- overstated the away side in 40,045 of 102,985 matchup rows — a plausible-looking
    -- number, wrong, and impossible to spot on screen because a head-to-head record is
    -- exactly the figure nobody arrives already knowing.
    select
        game_id,
        count(*)                                as series_games,
        sum(home_team_won)                      as series_home_team_wins,
        sum(away_team_won)                      as series_away_team_wins,
        sum(was_tied)                           as series_ties,
        min(prior_season)                       as series_first_season,
        max(prior_season)                       as series_last_season
    from (
        select
            cur.game_id,
            prior.season as prior_season,
            case when prior.home_team_id = cur.home_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.home_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end as home_team_won,
            case when prior.home_team_id = cur.away_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.away_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end as away_team_won,
            case when prior.home_points = prior.away_points then 1 else 0 end as was_tied
        from {{ ref('fct_game') }} cur
        join {{ ref('fct_game') }} prior
          on prior.home_team_id = cur.home_team_id
         and prior.away_team_id = cur.away_team_id
         and prior.game_id <> cur.game_id
        -- A RESULT, not merely a completed flag. Two games are marked completed with
        -- no score recorded, and counting them as meetings gave a head-to-head record
        -- of 0-0-0 over one meeting — a row that reconciles to nothing and reads as a
        -- rendering fault. A meeting with no result contributes no result.
        where prior.is_completed
          and prior.home_points is not null
          and prior.away_points is not null

        union all

        select
            cur.game_id,
            prior.season,
            case when prior.home_team_id = cur.home_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.home_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end,
            case when prior.home_team_id = cur.away_team_id
                      and prior.home_points > prior.away_points then 1
                 when prior.away_team_id = cur.away_team_id
                      and prior.away_points > prior.home_points then 1
                 else 0 end,
            case when prior.home_points = prior.away_points then 1 else 0 end
        from {{ ref('fct_game') }} cur
        join {{ ref('fct_game') }} prior
          on prior.home_team_id = cur.away_team_id
         and prior.away_team_id = cur.home_team_id
         and prior.game_id <> cur.game_id
        -- A RESULT, not merely a completed flag. Two games are marked completed with
        -- no score recorded, and counting them as meetings gave a head-to-head record
        -- of 0-0-0 over one meeting — a row that reconciles to nothing and reads as a
        -- rendering fault. A meeting with no result contributes no result.
        where prior.is_completed
          and prior.home_points is not null
          and prior.away_points is not null
    ) meetings
    group by game_id
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

    s.series_games, s.series_home_team_wins, s.series_away_team_wins, s.series_ties,
    s.series_first_season, s.series_last_season,
    ao_src.as_of_ts,
    mv_src.model_version as model_version_key,
    mv_src.attribution,
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.venue as venue_display,
    l.spread as spread_current,
    l.snapshot_ts,
    p.predicted_home_win_probability as home_win_probability,
    g.away_points - g.home_points as actual_margin,
    -- The same result read the other way round, so the page can put the actual margin
    -- beside predicted_margin_home_perspective without flipping a sign in the app. The
    -- storage convention stays away-minus-home everywhere; this is the display reading,
    -- and it is computed here because the app computing it would be the app owning a
    -- convention (G-3).
    g.home_points - g.away_points as actual_margin_home_perspective,
    -- The model's own coverage floor, carried as DATA so the Empty state is not a
    -- hardcoded "Week 5" string. CFBD does not ship current-season feature files until
    -- week 5, because the models need several weeks of this year's results before they can
    -- forecast this year's teams. Weeks 1-4 having no predictions is BY DESIGN and recurs
    -- every season — which makes it EMPTY (the data does not exist yet, and here is why),
    -- never Degraded (we have not built it).
    {{ var('prediction_training_week_floor', 5) }} as training_week_floor
from {{ ref('fct_game') }} g
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('fct_team_record') }} hr on hr.season = g.season and hr.team_id = g.home_team_id
left join {{ ref('fct_team_record') }} ar on ar.season = g.season and ar.team_id = g.away_team_id
left join latest_line l on l.game_id = g.game_id
left join latest_market m on m.game_id = g.game_id
left join latest_prediction p on p.game_id = g.game_id
left join series s on s.game_id = g.game_id
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'game') ao_src
-- AC-G.41: the licence-required attribution travels as DATA, so a page physically
-- cannot draw the model's numbers without it.
left join {{ ref('dim_model_version') }} mv_src
    on mv_src.model_name = p.model_name
   and mv_src.model_version = p.model_version
