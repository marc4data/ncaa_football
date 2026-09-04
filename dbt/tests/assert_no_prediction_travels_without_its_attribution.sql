-- A PREDICTION THAT LEAVES THE SITE MUST CARRY WHOSE PREDICTION IT IS.
--
-- The licence obligation is that cfdb's numbers are attributed as cfdb's own, built on a
-- commercially licensed training pack, and never presented as CollegeFootballData.com's.
-- The project's answer to that was structural rather than procedural: attribution is a
-- COLUMN on the serving view, sourced from dim_model_version, so a page physically cannot
-- render the numbers without having fetched the string that says whose they are.
--
-- WHY THIS TEST EXISTS NOW. R-221 removed the sheet-level model disclaimer from the Excel
-- workbook's Schedule tab, on Marc's instruction, while that sheet KEEPS six prediction
-- columns. What makes that safe is precisely the per-row attribution — which is strictly
-- stronger than a line in row 2, because it survives filtering, sorting and copy-paste into
-- another workbook, and row 2 does not.
--
-- "Strictly stronger" is only true while the column is actually populated. This turns the
-- assumption into a gate. Verified at zero violations across 110,879 rows on 2026-09-03,
-- 567 of which carry predictions; the equivalent property was already relied on for
-- srv_edge_finder and srv_model_performance and had NEVER been checked on srv_game, which
-- is the view the workbook reads.
--
-- NOT the reverse. Attribution present with no prediction is correct and common — no model
-- row for that game, so nothing to attribute. The failure is a populated forecast beside a
-- blank attribution.
select
    game_id,
    season,
    week,
    predicted_margin,
    home_win_probability,
    model_name,
    model_version_key
from {{ ref('srv_game') }}
where attribution is null
  and (predicted_margin     is not null
    or home_win_probability is not null
    or confidence_bucket    is not null
    or model_name           is not null
    or model_version_key    is not null)
