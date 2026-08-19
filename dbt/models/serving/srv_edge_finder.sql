{{ config(tags=['predictions']) }}
-- Edge Finder: one row per game x model x market, with the edge already computed.
--
-- The page's sliders are WHERE clauses over this table. No math in the app — which is why
-- the edge, the bucket and the out-of-sample flag are all columns rather than expressions.
--
-- SIGN CONVENTION. The upstream columns keep the pack's away-minus-home convention. This
-- view adds `margin_home_perspective` as an EXPLICITLY NAMED derived column so a page can
-- read a positive number as "home favoured by" without anything upstream being flipped.
-- The two live side by side on purpose: the derivation is auditable and the source is
-- unmodified.
with predictions as (
    select * from {{ ref('fct_prediction') }}
),
markets as (
    -- One row per bettable market, so a slider filters markets rather than columns.
    select
        p.*, 'moneyline' as market,
        p.home_win_probability_edge as edge_value,
        'probability' as edge_unit
    from predictions p
    -- Now populated: the de-vig in fct_market_probability supplies
    -- market_implied_home_win_probability, which the pack's exports leave blank.
    where p.home_win_probability_edge is not null

    union all

    -- Both edges are derived ONCE in fct_prediction and merely consumed here. Deriving in
    -- this view would force srv_model_performance and the Excel export to repeat the same
    -- formula independently, which is how definitions drift.
    select
        p.*, 'spread' as market,
        p.home_cover_edge as edge_value,
        'points' as edge_unit
    from predictions p
    where p.home_cover_edge is not null
)
select
    {{ surrogate_key(['markets.game_id', 'markets.model_name', 'markets.model_version', 'markets.split', 'markets.market']) }}
        as edge_finder_sk,
    markets.game_id,
    markets.season,
    markets.season_type,
    markets.week,
    markets.model_name,
    markets.model_version,
    markets.model_family,
    markets.split,
    markets.prediction_ts,
    markets.home_team,
    markets.away_team,
    markets.home_conference,
    markets.away_conference,
    markets.market,
    markets.edge_unit,
    markets.edge_value,
    abs(markets.edge_value) as edge_magnitude,
    markets.is_cover_edge_from_export,
    markets.is_wp_edge_from_export,
    markets.devig_method,
    markets.confidence_bucket,
    markets.spread,
    markets.predicted_margin,
    -- Derived, explicitly named, and the only place a home-perspective sign exists.
    -1 * markets.predicted_margin as predicted_margin_home_perspective,
    -1 * markets.spread           as spread_home_perspective,
    markets.predicted_home_win_probability,
    markets.market_implied_home_win_probability,
    markets.predicted_home_points,
    markets.predicted_away_points,
    markets.predicted_total_points,
    markets.actual_margin,
    markets.actual_home_cover,
    markets.home_win_correct,
    markets.cover_correct,
    markets.is_out_of_sample_week,
    markets.training_week_floor,
    -- The page must not present an extrapolated early-season edge as an actionable one.
    -- Precomputed rather than left to the app, so every consumer applies the same rule.
    case when is_out_of_sample_week then false else true end as is_default_actionable,
    case when is_out_of_sample_week
         then 'Before week ' || cast(training_week_floor as {{ dbt.type_string() }})
              || ' the model is extrapolating: the training set contains no regular-season '
              || 'game this early, because opponent-adjusted inputs need game history.'
    end as out_of_sample_note,
    ao_src.as_of_ts,
    mv_src.model_version as model_version_key,
    mv_src.attribution,
    markets.home_win_probability_edge
from markets
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'prediction') ao_src
-- AC-G.41: the licence-required attribution travels as DATA, so a page physically
-- cannot draw the model's numbers without it.
left join {{ ref('dim_model_version') }} mv_src
    on mv_src.model_name = markets.model_name
   and mv_src.model_version = markets.model_version
