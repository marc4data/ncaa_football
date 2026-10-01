{{ config(severity='error', tags=['predictions', 'full_refresh_only']) }}
-- ⚠️ `full_refresh_only` BECAUSE THE TWO SIDES REFRESH APART. `cfbd_scores_refresh` rebuilds
-- `dim_model_version` (an ancestor of `srv_game`) and NOT `srv_model_performance`, so inside
-- that DAG this would compare a fresh dimension against a view hours older and go red for a
-- reason that is not the defect — §2.2.5, and the shape that cost `publish_distributions` a
-- Friday afternoon (R-672). `ci/check_test_refresh_scope.py` names it; the weekly DAGs
-- rebuild the whole production set and are where this assertion has its authority.
-- 🚨 TWO COPIES OF A LICENCE STATEMENT DISAGREED, AND THE PAGE READ THE WRONG ONE.
-- A270 (cfdb-main-R-4405).
--
-- `claude_code/CLAUDE.md` names TWO homes for this wording — `dim_model_version.attribution`
-- and `srv_model_performance.attribution` — so that a page cannot render the numbers without
-- it. Naming two homes is exactly how they come to disagree (R-574), and they did: A269 keyed
-- the dimension by `model_name` so an own-features model would stop claiming the licensed
-- pack, and the serving view went on asserting the pack over EVERY model from a hardcoded
-- constant. The site published "built on a licensed CFB Model Training Pack" over a model
-- built from no pack row and no pack-derived column.
--
-- ✅ The view now JOINS the dimension, so there is one source. This asserts that it stays one:
-- every published row's attribution must be the attribution its own model version carries.
--
-- ⚠️ IT WALKS EVERY ROW rather than naming the model that broke, so it has real rows to work
-- on from the day it ships and does not go vacuous when a particular model is absent (R-760).
select
    p.model_name,
    p.model_version,
    p.attribution  as published_attribution,
    v.attribution  as dimension_attribution,
    'the published attribution is not the one this model version carries' as rule
from {{ ref('srv_model_performance') }} p
join {{ ref('dim_model_version') }} v
  on v.model_name = p.model_name
 and v.model_version = p.model_version
where p.attribution is distinct from v.attribution
