-- MARC'S RULE, AS A GATE: "only calculate it for opening line if it's different than the
-- ending line."
--
-- Applied per column, so a blank means "the market never changed its mind about THIS number"
-- and never "we did not look". The failure mode it guards is the quiet one: an open column
-- that repeats its closing neighbour reads as information and is noise, and with 85% of games
-- moving their line nobody would notice the 15% that should have been blank.
--
-- Every pair is listed rather than a representative one — the suppression is six separate
-- CASE expressions in the model and they can rot independently.
select
    game_team_sk,
    spread_open, spread_final,
    total_open, total_final,
    line_implied_points_open, line_implied_points_final,
    ats_margin_open, ats_margin_final
from {{ ref('srv_game_team') }}
where spread_open                = spread_final
   or total_open                 = total_final
   or line_implied_points_open   = line_implied_points_final
   or points_vs_line_implied_open = points_vs_line_implied_final
   or ats_margin_open            = ats_margin_final
