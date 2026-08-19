-- A written (game_id, model_name, model_version, split) row is never rewritten.
--
-- This is what makes Model Performance trustworthy over time: a figure computed in October
-- must still be reproducible in January. `model_version` is the content hash of the export
-- file, so a re-scored model is a DIFFERENT version and lands alongside its predecessor.
-- Two rows sharing the whole grain would mean a retrain had overwritten history in place.
select
    game_id,
    model_name,
    model_version,
    split,
    count(*) as row_count
from {{ ref('fct_prediction') }}
group by game_id, model_name, model_version, split
having count(*) > 1
