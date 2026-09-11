-- 🚨 `spread_open` AND `spread` ARE BOTH FROM THE HOME PERSPECTIVE, AND NOTHING CHECKED IT.
--
-- R-645/A102. `spread_move_from_open` is `spread - spread_open`, both taken verbatim from
-- CFBD with no sign flip on either. That subtraction is only meaningful while the two are on
-- the same perspective — flip one and every movement figure on the site inverts, silently,
-- while each individual number still looks like a plausible line.
--
-- ⚠️ A102 LOOKED FOR THE GUARD THAT WOULD CATCH THAT AND THERE WAS NONE. The prompt's premise
-- was that "the de-vig and the favourite side both key off this convention" — measured, they
-- key off `spread` and the moneylines. `spread_open` appears in exactly two places: this
-- subtraction, and srv_game_team's blank-when-unchanged suppression, which fires on EQUALITY
-- and so would not notice a flip either.
--
-- THE INVARIANT, AND IT IS STATISTICAL BECAUSE THE DEFECT IS: one game's line genuinely can
-- cross zero — a favourite becomes an underdog — so an individual opposite-signed row is not
-- a defect and must not fail. A flipped convention is not one row, it is all of them.
--
-- Measured 2026-09-11 on srv_line_movement: 674 of 25,909 rows carry opposite signs, 2.6%.
-- A flipped `spread_open` would send that to roughly 97%. The threshold is 15% — six times
-- the observed rate, and a sixth of what a flip produces, so it cannot fire on a busy market
-- and cannot miss an inverted one.
--
-- Returns ONE row when the share is exceeded, carrying the numbers, so the failure says how
-- far out it is rather than just that it is.
select
    count(*)                                                            as rows_compared,
    count(*) filter (where sign(spread) <> sign(spread_open))           as opposite_sign,
    round(100.0 * count(*) filter (where sign(spread) <> sign(spread_open))
          / nullif(count(*), 0), 1)                                     as pct_opposite
from {{ ref('srv_line_movement') }}
where spread is not null and spread_open is not null
  and spread <> 0 and spread_open <> 0
having count(*) filter (where sign(spread) <> sign(spread_open))
       > 0.15 * count(*)
