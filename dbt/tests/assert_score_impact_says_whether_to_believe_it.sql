-- A224 (cfdb-main-R-3011). `score_impact` AND ITS COHERENCE FLAG MUST AGREE WITH EACH OTHER.
--
-- 🚨 THE VALUE IS ALWAYS PUBLISHED AND THE FLAG IS WHAT SAYS WHETHER TO PRINT IT. That is the
-- AC-G.11 choice this round made explicitly: a null in `score_impact` already means *the
-- snapshots are missing*, so making it ALSO mean *the snapshots disagree* would be an absence
-- that does not say which absence it is.
--
-- ⚠️ THE RULE IS `matchup.py`'s, TO THE LETTER, and this asserts the column carries it rather
-- than something near it. 📊 It is false on 3,113 of 87,897 drives — 3.54%, which is that
-- page's own published suppression rate to two decimal places.
--
-- ⚠️ AND THE LEGAL SET IS THE POINT OF THE SECOND CLAUSE: what one scoring play can put on a
-- board from the offense's point of view is a safety, a field goal, a touchdown alone or with
-- either conversion — positive or negative — or nothing. A render caught a FIELD GOAL worth
-- -4 passing the first check, which is why there are two.
select
    drive_id,
    season,
    drive_result,
    is_scoring_drive,
    score_impact,
    is_score_impact_coherent
from {{ ref('fct_drive') }}
where
    -- the model coalesces this flag, so a null here is the model breaking its own contract
    is_score_impact_coherent is null
 or is_score_impact_coherent <> coalesce(
        coalesce(is_scoring_drive, false) = (score_impact <> 0)
        and score_impact in (0, 2, 3, 6, 7, 8, -2, -3, -6, -7, -8),
        false)
    -- a coherent row whose value is not a score anything can produce
 or (is_score_impact_coherent
     and score_impact not in (0, 2, 3, 6, 7, 8, -2, -3, -6, -7, -8))
