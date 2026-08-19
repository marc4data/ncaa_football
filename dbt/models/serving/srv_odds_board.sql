-- Odds Board: one row per game per provider, latest snapshot.
--
-- The whole page IS the provider comparison, so unlike Team page there is no partial
-- fallback — which is why this view had to be built rather than deferred. Everything it
-- needs already existed: fct_betting_line is populated, fct_market_probability supplies the
-- de-vigged probabilities, and fct_prediction supplies the model column.
with latest as (
    select *
    from (
        select b.*,
               row_number() over (partition by b.game_id, b.provider_key
                                  order by b.snapshot_ts desc) as recency
        from {{ ref('fct_betting_line') }} b
    ) r
    where recency = 1
),
prediction as (
    -- One model per game, most recent. Predictions APPEND on re-score, so without this the
    -- board would multiply every provider row by the number of model versions.
    select game_id, model_name, model_version, predicted_margin, home_cover_edge
    from (
        -- Prefer a model that actually populates the column this board shows.
        --
        -- Ordering by recency alone picked a win-probability model, which has no
        -- predicted_margin at all — so the board rendered attribution for 1,701 rows and a
        -- margin for none. Six of the seven models are probability models, so "most recent"
        -- loses the margin almost every time. Preferring a non-null margin is not cherry-
        -- picking a better number; it is picking the model that answers the question asked.
        select p.*, row_number() over (
                   partition by p.game_id
                   order by case when p.predicted_margin is not null then 0 else 1 end,
                            p.prediction_ts desc, p.model_version desc) as recency
        from {{ ref('fct_prediction') }} p
    ) r
    where recency = 1
),
-- "Best available" is a column, not an app-side max(): AC-11.3 forbids the app choosing.
-- Best for a home backer is the largest spread (least negative), evaluated per game.
best AS (
    select game_id, max(spread) as best_home_spread, min(spread) as best_away_spread
    from latest
    group by game_id
)
select
    {{ surrogate_key(['l.game_id', 'l.provider_key']) }} as odds_board_sk,
    l.game_id,
    l.season,
    l.week,
    l.season_type,
    {{ to_local_timestamp('g.start_date') }} as start_date_et,
    g.home_team_id, g.home_team as home_team_display, h.team_slug as home_team_slug,
    h.logo_source_url as home_logo_url, h.color_on_light as home_color_on_light,
    g.away_team_id, g.away_team as away_team_display, a.team_slug as away_team_slug,
    a.logo_source_url as away_logo_url, a.color_on_light as away_color_on_light,

    l.provider_key,
    p.provider_name as provider_display,
    l.spread,
    l.spread_open,
    l.over_under                as total,
    l.over_under_open           as total_open,
    l.home_moneyline,
    l.away_moneyline,
    mp.market_implied_home_win_probability as home_implied_probability,
    mp.market_implied_away_win_probability as away_implied_probability,
    mp.devig_method,
    l.snapshot_ts,
    true                        as is_latest_snapshot,
    pr.predicted_margin,
    pr.home_cover_edge,
    pr.model_name               as model_version_key,
    mv.attribution,
    -- Precomputed so the app highlights rather than decides (AC-11.3).
    l.spread = b.best_home_spread as is_best_home_spread,
    l.spread = b.best_away_spread as is_best_away_spread,
    ao.as_of_ts
from latest l
left join {{ ref('fct_game') }} g on g.game_id = l.game_id
left join {{ ref('dim_team') }} h on h.season = g.season and h.team_id = g.home_team_id
left join {{ ref('dim_team') }} a on a.season = g.season and a.team_id = g.away_team_id
left join {{ ref('dim_provider') }} p on p.provider_key = l.provider_key
left join {{ ref('fct_market_probability') }} mp
    on mp.betting_line_sk = l.betting_line_sk
left join prediction pr on pr.game_id = l.game_id
left join {{ ref('dim_model_version') }} mv
    on mv.model_name = pr.model_name and mv.model_version = pr.model_version
left join best b on b.game_id = l.game_id
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'market') ao
