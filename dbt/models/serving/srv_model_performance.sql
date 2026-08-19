{{ config(tags=['predictions']) }}
-- Model Performance: accuracy and calibration, pre-aggregated by segment.
--
-- Honest by construction, which is the point of shipping it early. The measured baseline is
-- 49.4% ATS — behind the market on every axis — and a page that only rendered once the
-- model was good would be a page that never told the truth about it.
--
-- Segmented by model, split, season and out-of-sample status. `split` is carried because a
-- train-split number is not a claim about the future and must never be shown as one.
with scored as (
    select * from {{ ref('fct_prediction') }}
    where home_points is not null
),
aggregated as (
    select
        model_name,
        model_version,
        model_family,
        split,
        season,
        is_out_of_sample_week,
        count(*)                                                        as games,
        avg(absolute_margin_error)                                      as mae,
        avg(margin_error)                                               as mean_margin_error,
        avg(brier_score_component)                                      as brier_score,
        avg(log_loss_component)                                         as log_loss,
        sum(case when home_win_correct then 1 else 0 end)               as winner_correct,
        count(home_win_correct)                                         as winner_scored,
        sum(case when cover_correct then 1 else 0 end)                  as cover_correct_count,
        -- Pushes are blank in the contract and excluded from cover accuracy, so the
        -- denominator counts only rows where a cover result actually exists.
        count(cover_correct)                                            as cover_scored
    from scored
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week
)
select
    {{ surrogate_key(['model_name', 'model_version', 'split', 'season', 'is_out_of_sample_week']) }}
        as model_performance_sk,
    model_name,
    model_version,
    model_family,
    split,
    season,
    is_out_of_sample_week,
    games,
    round(cast(mae as numeric), 3)               as mean_absolute_margin_error,
    round(cast(mean_margin_error as numeric), 3) as mean_margin_error,
    round(cast(brier_score as numeric), 5)       as brier_score,
    round(cast(log_loss as numeric), 5)          as log_loss,
    winner_correct,
    winner_scored,
    case when winner_scored > 0
         then round(100.0 * winner_correct / winner_scored, 1) end as winner_accuracy_pct,
    cover_correct_count,
    cover_scored,
    case when cover_scored > 0
         then round(100.0 * cover_correct_count / cover_scored, 1) end as ats_accuracy_pct,
    -- Licence requirement, carried as data so a page cannot render the numbers without it.
    'cfdb model, built on a licensed CFB Model Training Pack (2026 Edition). '
        || 'Not an official CollegeFootballData.com prediction.' as attribution
from aggregated
