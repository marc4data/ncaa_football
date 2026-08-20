{{ config(tags=['predictions']) }}
-- Model Performance: accuracy and calibration, pre-aggregated by segment.
--
-- Honest by construction, which is the point of shipping it early. The measured baseline is
-- 49.4% ATS — behind the market on every axis — and a page that only rendered once the
-- model was good would be a page that never told the truth about it.
--
-- `split` is carried because a train-split number is not a claim about the future and must
-- never be shown as one.
--
-- SEGMENTS. The header comment promised "pre-aggregated by segment" and the view had one
-- grain, so the claim was aspirational. It is now literal: the same measures are computed
-- at five cuts and stacked long, with `segment_type` and `segment_value` saying which cut a
-- row belongs to.
--
--   overall       one row per model. What the headline table shows.
--   week          does the model decay, or improve, as the season accumulates data.
--   conference    where it is confident and wrong.
--   confidence    does the model's own confidence label mean anything.
--   probability   CALIBRATION: predicted probability decile against realised win rate.
--
-- Long rather than wide, because the alternative is a column per week per measure and a
-- view that has to be altered every time a new cut is asked for. A page filters on
-- segment_type; nothing has to change here to add a chart.
--
-- CONSUMERS MUST FILTER. A query that does not name a segment_type now returns every cut
-- stacked together, which is a table of numbers at incompatible grains. The headline table
-- and the Excel sheet both filter to 'overall'.
with scored as (
    select * from {{ ref('fct_prediction') }}
    where home_points is not null
),

-- One row per (prediction, conference the game belongs to). A game has two conferences and
-- is counted under both: "how does the model do on SEC games" includes a Big Ten team's
-- visit to Tuscaloosa, and excluding it would answer a different question. The consequence
-- is that summing the conference rows exceeds the overall row, which is why segment_type is
-- carried and a reader is never invited to add these up.
by_conference as (
    select s.*, s.home_conference as conference_name
    from scored s
    where s.home_conference is not null

    union all

    select s.*, s.away_conference
    from scored s
    where s.away_conference is not null
      -- A conference game would otherwise contribute twice to its own conference.
      and s.away_conference is distinct from s.home_conference
),

segmented as (

    select model_name, model_version, model_family, split, season, is_out_of_sample_week,
           'overall'                                     as segment_type,
           cast(null as {{ dbt.type_string() }})         as segment_value,
           0                                             as segment_order,
           {{ prediction_measures() }}
    from scored
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week

    union all

    select model_name, model_version, model_family, split, season, is_out_of_sample_week,
           'week', cast(week as {{ dbt.type_string() }}), week,
           {{ prediction_measures() }}
    from scored
    where week is not null
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week,
             week

    union all

    select model_name, model_version, model_family, split, season, is_out_of_sample_week,
           'conference', conference_name, 0,
           {{ prediction_measures() }}
    from by_conference
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week,
             conference_name

    union all

    -- The pack writes an empty string where it has no bucket. Normalised to NULL here, so
    -- "unlabelled" is one segment rather than a blank row that looks like a rendering fault.
    select model_name, model_version, model_family, split, season, is_out_of_sample_week,
           'confidence',
           coalesce(nullif(trim(confidence_bucket), ''), 'unlabelled'),
           case lower(trim(confidence_bucket))
                when 'low' then 1 when 'medium' then 2 when 'high' then 3 else 9 end,
           {{ prediction_measures() }}
    from scored
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week,
             confidence_bucket

    union all

    -- Calibration. Deciles of the model's own predicted probability, so
    -- mean_predicted_home_win_probability can be read against actual_home_win_rate: a
    -- calibrated model has them equal in every bucket. This is the cut that says whether a
    -- 70% is worth 70 cents, and no accuracy figure answers it.
    select model_name, model_version, model_family, split, season, is_out_of_sample_week,
           'probability',
           cast(floor(predicted_home_win_probability * 10) * 10
                as {{ dbt.type_int() }}) || '-' ||
           cast(floor(predicted_home_win_probability * 10) * 10 + 10
                as {{ dbt.type_int() }}) || '%',
           cast(floor(predicted_home_win_probability * 10) as {{ dbt.type_int() }}),
           {{ prediction_measures() }}
    from scored
    where predicted_home_win_probability is not null
      -- 1.0 would floor into an eleventh bucket of its own.
      and predicted_home_win_probability < 1
    group by model_name, model_version, model_family, split, season, is_out_of_sample_week,
             floor(predicted_home_win_probability * 10)
)

select
    {{ surrogate_key(['model_name', 'model_version', 'split', 'season',
                      'is_out_of_sample_week', 'segment_type', 'segment_value']) }}
        as model_performance_sk,
    model_name,
    model_version,
    model_family,
    split,
    season,
    is_out_of_sample_week,
    segment_type,
    segment_value,
    -- Display order within a segment type, so a page renders week 5 before week 10 and low
    -- before high without knowing what any of those mean.
    segment_order,
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
    -- The two calibration columns. Equal values mean a calibrated model; a gap between them
    -- is the size and direction of its over- or under-confidence.
    round(cast(mean_predicted_probability as numeric), 4)
        as mean_predicted_home_win_probability,
    case when winner_scored > 0
         then round(cast(actual_home_wins as numeric) / winner_scored, 4) end
        as actual_home_win_rate,
    -- Licence requirement, carried as data so a page cannot render the numbers without it.
    'cfdb model, built on a licensed CFB Model Training Pack (2026 Edition). '
        || 'Not an official CollegeFootballData.com prediction.' as attribution,
    ao_src.as_of_ts
from segmented
-- AC-G.35: the page's "as of" timestamp is a COLUMN, sourced from when this view's
-- underlying data was last loaded, never from now() in the app. Per-domain rather than
-- global: a betting line and a 1936 poll have very different notions of fresh.
cross join (select as_of_ts from {{ ref('mart_as_of') }} where domain = 'prediction') ao_src
