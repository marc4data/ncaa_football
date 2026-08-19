{{ config(materialized='table', tags=['predictions']) }}
-- One row per game x model_name x model_version x split. Append-only.
--
-- The pack's grain is (game_id, model_name, split). `model_version` and `prediction_ts` are
-- ours, and they are what make in-season re-scoring safe: a retrain lands alongside its
-- predecessor rather than replacing it, so a Model Performance figure computed last week
-- cannot quietly change this week.
--
-- The 42-column contract is adopted essentially verbatim. Columns are NOT renamed to house
-- style: when a number here disagrees with the pack's own leaderboard, the first question
-- will be whether they are the same quantity, and identical names make that answerable.
--
-- SIGN CONVENTION, once more because it governs every derived figure below:
--     margin = away - home, so a NEGATIVE margin means the HOME team won
--     spread < 0 means the HOME team was favoured
--     home_cover is TRUE when margin < spread
with predictions as (
    select * from {{ ref('stg_predictions') }}
),

-- The market's de-vigged probability, latest snapshot per game.
--
-- Latest rather than an average across books: the Edge Finder compares the model against
-- the price a bet would actually be placed at, and averaging several books produces a
-- number nobody can take.
market as (
    -- game_id is aliased so nothing in the wide select list below collides with it: the
    -- fact selects most columns unqualified, and a bare `game_id` would be ambiguous.
    select game_id as market_game_id, market_implied_home_win_probability, devig_method
    from (
        select
            game_id,
            market_implied_home_win_probability,
            devig_method,
            row_number() over (partition by game_id
                               order by snapshot_ts desc, provider_key) as recency
        from {{ ref('fct_market_probability') }}
    ) ranked
    where recency = 1
)
select
    {{ surrogate_key(['game_id', 'model_name', 'model_version', 'split']) }} as prediction_sk,

    -- Grain
    game_id,
    model_name,
    model_version,
    split,
    prediction_ts,
    {{ surrogate_key(['model_name', 'model_version']) }} as model_version_sk,

    -- Game context, as exported
    season,
    season_type,
    week,
    {{ surrogate_key(['season', 'season_type', 'week']) }} as week_sk,
    home_team,
    away_team,
    home_conference,
    away_conference,
    model_family,
    target,

    -- Actuals (null for unplayed games)
    home_points,
    away_points,
    actual_margin,
    actual_total_points,
    actual_home_win,
    actual_winner,
    spread,
    actual_home_cover,

    -- Predictions
    predicted_home_points,
    predicted_away_points,
    predicted_margin,
    predicted_total_points,
    predicted_home_win_probability,
    raw_home_win_probability,
    calibrated_home_win_probability,
    predicted_home_win,
    predicted_winner,
    predicted_home_cover,

    -- MARKET COMPARISON AND EDGE, derived here rather than in a serving view.
    --
    -- The pack's notebooks leave all three blank — measured on the first real load, 0 of
    -- 3,402 rows populated, while spread (3,402) and predicted_margin (1,134) both are. The
    -- export contract permits "leave unsupported fields blank" and every notebook takes it.
    --
    -- These are per-prediction measures, so they belong at this grain. Deriving them in
    -- srv_edge_finder would force srv_model_performance and the Excel export to re-derive
    -- them independently — three copies of one formula, which is how definitions drift.
    -- Derived once here, consumed everywhere.
    --
    -- Both formulas are the CONTRACT'S OWN, applied verbatim, not invented:
    --     home_cover_edge          = spread - predicted_margin
    --     home_win_probability_edge = predicted_home_win_probability
    --                                 - market_implied_home_win_probability
    coalesce(p.market_implied_home_win_probability,
             m.market_implied_home_win_probability) as market_implied_home_win_probability,
    coalesce(
        p.home_win_probability_edge,
        p.predicted_home_win_probability
            - coalesce(p.market_implied_home_win_probability,
                       m.market_implied_home_win_probability)
    ) as home_win_probability_edge,
    coalesce(p.home_cover_edge, p.spread - p.predicted_margin) as home_cover_edge,

    -- Provenance. Which values came from the export and which from this model is never
    -- invisible, and a later pack release that starts populating them changes these flags
    -- rather than silently changing the numbers.
    p.home_cover_edge is not null                as is_cover_edge_from_export,
    p.home_win_probability_edge is not null      as is_wp_edge_from_export,
    p.market_implied_home_win_probability is not null as is_market_prob_from_export,
    m.devig_method,
    confidence_bucket,

    -- Evaluation
    margin_error,
    absolute_margin_error,
    home_win_correct,
    cover_correct,
    brier_score_component,
    log_loss_component,

    -- OUT-OF-SAMPLE HONESTY (Task 3).
    --
    -- The pack trains on regular-season games from WEEK 5 ONWARD — verified against the
    -- training data, which contains no regular-season row below week 5 — because the
    -- opponent-adjusted inputs are meaningless before a team has a game history. There is
    -- therefore no in-sample analogue for an early-season game, and the 2026 season opens
    -- on 2026-08-27 in week 0.
    --
    -- A Week 1 edge is extrapolation and a Week 8 edge is inference. They must not render
    -- identically, so the distinction is carried in the data rather than left to the page.
    case
        when season_type = 'regular' and week < {{ var('prediction_training_week_floor', 5) }}
        then true else false
    end as is_out_of_sample_week,
    {{ var('prediction_training_week_floor', 5) }} as training_week_floor
from predictions p
left join market m on m.market_game_id = p.game_id
