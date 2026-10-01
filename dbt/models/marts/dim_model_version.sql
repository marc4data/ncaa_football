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
    -- 🚨 A269 (cfdb-main-R-4351). THESE THREE WERE CONSTANTS AND TWO OF THEM ARE LICENCE AND
    -- PROVENANCE STATEMENTS, so a constant made the page assert something untrue the moment a
    -- model arrived that was not built from the pack.
    --
    -- `cfdb_wtc_c1_own_features_tuned` uses NO row of the pack's training data and NO column
    -- derived from it: its features are computed by `modeling/own_features.py` from CFBD API
    -- data on disk plus `staging.stg_games` (cfdb-wtc-R-2530's provenance section). So:
    --
    --  * it must NOT carry "built on a licensed CFB Model Training Pack" — that is false;
    --  * it must NOT carry "Not an official CollegeFootballData.com prediction" — that
    --    sentence is a PACK REQUIREMENT, and a model using no pack material sits under the
    --    CFBD API terms instead, where this project's own boundary doc records attribution
    --    as "Optional (do it anyway)". The footer carries the CFBD credit for every page.
    --
    -- ⚠️ THE PACK'S SIX MODELS KEEP EXACTLY THE TEXT THEY ALREADY HAD. Their branch below is
    -- byte-for-byte what this file carried before, deliberately: one change per reason.
    case when model_name = 'cfdb_wtc_c1_own_features_tuned'
         then 'walk-forward 2018–2024; test = 2025, scored once'
         else 'train <= 2023, validate = 2024, test = 2025'
    end as split_definition,
    -- The pack version is the feature-set version: the 86 training columns are fixed by the
    -- edition, so the edition identifies them. The own-features model names its own set.
    case when model_name = 'cfdb_wtc_c1_own_features_tuned'
         then 'M4D own features v1 (2026-09)'
         else 'CFB Model Training Pack 2026'
    end as feature_set_version,
    -- Licence requirement for the pack's models, carried in the data so a page cannot render
    -- without it. ⚠️ `M4D` is the BRAND; `cfdb` is only the VS Code project name and reads as
    -- a reference to CollegeFootballData.com, which is the last thing an own-model should be
    -- branded with (cfdb-main-R-3650).
    case when model_name = 'cfdb_wtc_c1_own_features_tuned'
         then 'M4D original model — every feature computed in-house from '
              || 'CollegeFootballData.com data.'
         else 'M4D model, built on a licensed CFB Model Training Pack (2026 Edition). '
              || 'Not an official CollegeFootballData.com prediction.'
    end as attribution
from versions
