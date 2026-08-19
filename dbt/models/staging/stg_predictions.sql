-- Model predictions, typed from the pack's 42-column export contract.
--
-- THE SIGN CONVENTION IS PRESERVED, NOT NORMALISED. The pack uses, and this was verified
-- against all 5,133 training rows before anything was built:
--
--     actual_margin = away_points - home_points      <- AWAY MINUS HOME
--     margin < 0  means the HOME team won
--     spread < 0  means the HOME team was favoured   (home wins 74.4% of those games,
--                                                     against 31.4% when spread > 0)
--
-- That reads backwards, and flipping it here is the single most damaging thing this model
-- could do: every cover flag, edge and ATS figure would invert while still looking
-- plausible. A home-perspective margin is derived in the serving layer instead, named so
-- that it cannot be mistaken for the source column.
--
-- Booleans arrive as Python's "True"/"False" text and blanks mean "not applicable" — a
-- push, or a field the model does not populate — so they are read as text and normalised
-- to a real boolean with nulls preserved rather than coerced to false.
{{ config(tags=['predictions']) }}

with source as (
    select
        source_file,
        model_version,
        prediction_ts,
        row_number,
        payload
    from {{ source('raw', 'raw_model_prediction') }}
),
typed as (
    select
        source_file,
        model_version,
        prediction_ts,
        row_number,
        cast({{ json_get_string('payload', 'game_id') }} as bigint)   as game_id,
        cast({{ json_get_string('payload', 'season') }} as int)       as season,
        {{ json_get_string('payload', 'season_type') }}               as season_type,
        cast({{ json_get_string('payload', 'week') }} as int)         as week,
        {{ json_get_string('payload', 'home_team') }}                 as home_team,
        {{ json_get_string('payload', 'away_team') }}                 as away_team,
        {{ json_get_string('payload', 'home_conference') }}           as home_conference,
        {{ json_get_string('payload', 'away_conference') }}           as away_conference,
        {{ json_get_string('payload', 'split') }}                     as split,
        {{ json_get_string('payload', 'model_name') }}                as model_name,
        {{ json_get_string('payload', 'model_family') }}              as model_family,
        {{ json_get_string('payload', 'target') }}                    as target,

        {{ safe_numeric(json_get_string('payload', 'home_points')) }}          as home_points,
        {{ safe_numeric(json_get_string('payload', 'away_points')) }}          as away_points,
        {{ safe_numeric(json_get_string('payload', 'actual_margin')) }}        as actual_margin,
        {{ safe_numeric(json_get_string('payload', 'actual_total_points')) }}  as actual_total_points,
        {{ json_get_string('payload', 'actual_home_win') }}                    as actual_home_win_raw,
        {{ json_get_string('payload', 'actual_winner') }}                      as actual_winner,
        {{ safe_numeric(json_get_string('payload', 'spread')) }}               as spread,
        {{ json_get_string('payload', 'actual_home_cover') }}                  as actual_home_cover_raw,

        {{ safe_numeric(json_get_string('payload', 'predicted_home_points')) }} as predicted_home_points,
        {{ safe_numeric(json_get_string('payload', 'predicted_away_points')) }} as predicted_away_points,
        {{ safe_numeric(json_get_string('payload', 'predicted_margin')) }}      as predicted_margin,
        {{ safe_numeric(json_get_string('payload', 'predicted_total_points')) }} as predicted_total_points,
        {{ safe_numeric(json_get_string('payload', 'predicted_home_win_probability')) }} as predicted_home_win_probability,
        {{ safe_numeric(json_get_string('payload', 'raw_home_win_probability')) }} as raw_home_win_probability,
        {{ safe_numeric(json_get_string('payload', 'calibrated_home_win_probability')) }} as calibrated_home_win_probability,
        {{ json_get_string('payload', 'predicted_home_win') }}                  as predicted_home_win_raw,
        {{ json_get_string('payload', 'predicted_winner') }}                    as predicted_winner,
        {{ json_get_string('payload', 'predicted_home_cover') }}                as predicted_home_cover_raw,

        {{ safe_numeric(json_get_string('payload', 'market_implied_home_win_probability')) }} as market_implied_home_win_probability,
        {{ safe_numeric(json_get_string('payload', 'home_win_probability_edge')) }} as home_win_probability_edge,
        {{ safe_numeric(json_get_string('payload', 'home_cover_edge')) }}       as home_cover_edge,
        {{ json_get_string('payload', 'confidence_bucket') }}                   as confidence_bucket,
        {{ safe_numeric(json_get_string('payload', 'margin_error')) }}          as margin_error,
        {{ safe_numeric(json_get_string('payload', 'absolute_margin_error')) }} as absolute_margin_error,
        {{ json_get_string('payload', 'home_win_correct') }}                    as home_win_correct_raw,
        {{ json_get_string('payload', 'cover_correct') }}                       as cover_correct_raw,
        {{ safe_numeric(json_get_string('payload', 'brier_score_component')) }} as brier_score_component,
        {{ safe_numeric(json_get_string('payload', 'log_loss_component')) }}    as log_loss_component
    from source
)
select
    *,
    {{ text_to_boolean('actual_home_win_raw') }}     as actual_home_win,
    {{ text_to_boolean('actual_home_cover_raw') }}   as actual_home_cover,
    {{ text_to_boolean('predicted_home_win_raw') }}  as predicted_home_win,
    {{ text_to_boolean('predicted_home_cover_raw') }} as predicted_home_cover,
    {{ text_to_boolean('home_win_correct_raw') }}    as home_win_correct,
    {{ text_to_boolean('cover_correct_raw') }}       as cover_correct
from typed
