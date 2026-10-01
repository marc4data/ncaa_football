{{ config(severity='error', tags=['predictions']) }}
-- 🚨 A MODEL'S ATTRIBUTION IS A LICENCE AND PROVENANCE STATEMENT, AND IT SHIPS TO A READER.
-- A269 (cfdb-main-R-4351).
--
-- `dim_model_version` carried `attribution`, `feature_set_version` and `split_definition` as
-- CONSTANTS, asserting for EVERY model that it was "built on a licensed CFB Model Training
-- Pack (2026 Edition)". That was true of the only seven models that had ever been loaded and
-- became false the moment an own-features model arrived — and it is the kind of false that a
-- page renders in good faith, because the sentence is carried in the data precisely so a page
-- cannot render the numbers without it.
--
-- THE RULE: a model may claim the pack only if it IS one of the pack's models.
--
-- ⚠️ THE PACK'S SEVEN NAMES ARE LISTED EXPLICITLY, NOT INFERRED. There is no column saying
-- "this came from the pack" — the attribution string IS that claim — so a test that derived
-- the allowed set from the same string it is checking would assert that a thing equals
-- itself. The list is the pack's six withdrawn models plus `random_forest_score`, which is
-- the set `site/lib/models.py` names and the set the pack's seven notebooks export.
--
-- 🚨 R-760 — THIS TEST IS WRITTEN SO IT CAN ACTUALLY FIRE, WHICH TOOK CARE. The obvious
-- phrasing ("the own-features model must not claim the pack") selects on a model_name that
-- does not exist until A270 loads it, so it would pass on ZERO ROWS and look like a guard for
-- as long as nobody loaded anything. This phrasing instead walks EVERY row of the dimension
-- and asks whether its claim is permitted, so it has real rows to work on from the day it
-- ships — all seven pack models exercise it today.
--
-- ✅ PROVEN RED BY A269 BEFORE THE FIX, on real warehouse rows: with `random_forest_score`
-- removed from the list below, it returned that model's live row. The mechanism reaches the
-- data; it is not decoration.
select
    model_name,
    model_version,
    attribution,
    'this model claims the CFB Model Training Pack and is not one of its models' as rule
from {{ ref('dim_model_version') }}
where attribution like '%CFB Model Training Pack%'
  and model_name not in (
      -- the pack's six line-fed models, withdrawn from the site
      'ridge_margin_expanded',
      'xgboost_home_win_calibrated',
      'logistic_home_win_c_0.25',
      'xgboost_home_win_shap_explained',
      'stacked_ensemble_home_win',
      'fastai_home_win',
      -- and the one the site still publishes
      'random_forest_score',
      -- 🚨 `linear_margin` IS A PACK MODEL AND THE LIST WAS WRONG WITHOUT IT — caught by CI,
      -- which is the only place it appears (§2.3.3: a test that names production's rows runs
      -- in one place unless it also knows the fixture's). The pack's notebook 01 exports
      -- `linear_margin_predictions.csv`, which is `EXPECTED_FILES[0]`; production's rows for
      -- that model carry `ridge_margin_expanded` and `ci/fixtures.sql:4128` carries
      -- `linear_margin`. Two names for one pack notebook, and BOTH are entitled to claim the
      -- pack — which is what this test is actually about. ⚠️ This is the list widening to
      -- match the rule, not the rule relaxing to match a failure.
      'linear_margin'
  )
