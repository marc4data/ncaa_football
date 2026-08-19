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
    -- NOT derived. home_win_probability_edge needs market_implied_home_win_probability,
    -- which the notebooks also leave blank (0 of 3,402). It could be recovered from the
    -- moneylines in fct_betting_line, but only by choosing a de-vig method — and that is a
    -- modelling decision, not a load-time one. Raised in DECISIONS NEEDED rather than
    -- guessed at, so this market stays empty until it is settled.
    where p.home_win_probability_edge is not null

    union all

    -- The pack's notebooks leave home_cover_edge BLANK — the export contract permits
    -- "leave unsupported fields blank", and none of the seven notebooks fills it. Measured
    -- on the first real load: 0 of 3,402 rows populated, while spread (3,402) and
    -- predicted_margin (1,134) both are.
    --
    -- So it is computed here from the contract's OWN definition, verbatim:
    --     home_cover_edge = spread - predicted_margin
    -- That is applying a documented formula to columns we have, not inventing a metric.
    -- `is_edge_derived` records which rows came from the export and which from this
    -- calculation, so the distinction is never invisible.
    select
        p.*, 'spread' as market,
        coalesce(p.home_cover_edge, p.spread - p.predicted_margin) as edge_value,
        'points' as edge_unit
    from predictions p
    where coalesce(p.home_cover_edge, p.spread - p.predicted_margin) is not null
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
    home_cover_edge is not null as is_edge_from_export,
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
