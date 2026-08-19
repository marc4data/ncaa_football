{{ config(materialized='table', tags=['predictions']) }}
-- One row per model version actually loaded: what produced a prediction, and when.
--
-- Derived from the exports rather than declared, because a declared list drifts the moment
-- a notebook is re-run. `model_version` is the content hash of the export file, which is
-- what makes re-scoring append instead of overwrite — the same file reloaded is the same
-- version, a re-scored file is a new one, and Model Performance can never be silently
-- rewritten by a retrain.
--
-- `trained_at` is the export file's modification time, which is a proxy: the pack's
-- contract carries no training timestamp, so this is when the predictions were WRITTEN and
-- not necessarily when the model was fitted. Named honestly rather than precisely; see
-- DECISIONS NEEDED in the PR.
with versions as (
    select
        model_name,
        model_version,
        max(model_family)    as model_family,
        max(target)          as target,
        min(prediction_ts)   as trained_at,
        max(source_file)     as source_file,
        count(*)             as prediction_count,
        count(distinct split) as split_count,
        min(season)          as first_season,
        max(season)          as last_season
    from {{ ref('stg_predictions') }}
    group by model_name, model_version
)
select
    {{ surrogate_key(['model_name', 'model_version']) }} as model_version_sk,
    model_name,
    model_version,
    model_family,
    target,
    trained_at,
    source_file,
    prediction_count,
    split_count,
    first_season,
    last_season,
    -- The pack's default split, recorded so a page can state it rather than assume it.
    'train <= 2023, validate = 2024, test = 2025' as split_definition,
    -- The pack version is the feature-set version: the 86 training columns are fixed by the
    -- edition, so the edition identifies them.
    'CFB Model Training Pack 2026' as feature_set_version,
    -- Licence requirement, carried in the data so a page cannot render without it.
    'cfdb model, built on a licensed CFB Model Training Pack (2026 Edition). '
        || 'Not an official CollegeFootballData.com prediction.' as attribution
from versions
