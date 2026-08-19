{{ config(tags=['predictions', 'postgres_only']) }}
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
    where p.home_win_probability_edge is not null

    union all

    select
        p.*, 'spread' as market,
        p.home_cover_edge as edge_value,
        'points' as edge_unit
    from predictions p
    where p.home_cover_edge is not null
)
select
    {{ surrogate_key(['game_id', 'model_name', 'model_version', 'split', 'market']) }}
        as edge_finder_sk,
    game_id,
    season,
    season_type,
    week,
    model_name,
    model_version,
    model_family,
    split,
    prediction_ts,
    home_team,
    away_team,
    home_conference,
    away_conference,
    market,
    edge_unit,
    edge_value,
    abs(edge_value) as edge_magnitude,
    confidence_bucket,
    spread,
    predicted_margin,
    -- Derived, explicitly named, and the only place a home-perspective sign exists.
    -1 * predicted_margin as predicted_margin_home_perspective,
    -1 * spread           as spread_home_perspective,
    predicted_home_win_probability,
    market_implied_home_win_probability,
    predicted_home_points,
    predicted_away_points,
    predicted_total_points,
    actual_margin,
    actual_home_cover,
    home_win_correct,
    cover_correct,
    is_out_of_sample_week,
    training_week_floor,
    -- The page must not present an extrapolated early-season edge as an actionable one.
    -- Precomputed rather than left to the app, so every consumer applies the same rule.
    case when is_out_of_sample_week then false else true end as is_default_actionable,
    case when is_out_of_sample_week
         then 'Before week ' || cast(training_week_floor as {{ dbt.type_string() }})
              || ' the model is extrapolating: the training set contains no regular-season '
              || 'game this early, because opponent-adjusted inputs need game history.'
    end as out_of_sample_note
from markets
