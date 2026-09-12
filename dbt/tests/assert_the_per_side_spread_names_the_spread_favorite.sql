{{ config(severity='error', tags=['scores_refresh_only']) }}
-- 🚨 TAGGED `scores_refresh_only`, AND A GUARD SAID SO BEFORE A GAME DAY DID. R-685.
--
-- ci/check_test_refresh_scope.py, on this test's first run: it reads `fct_game_market`, which
-- `cfbd_lines_snapshot` rebuilds, against `srv_game_team`, which it does not — so between the two
-- refreshes it would compare a fresh market mart against a stale per-side spread, go red for a
-- reason that is not the defect, and stop the site publishing. That is R-672 exactly.
--
-- ✅ `cfbd_scores_refresh` rebuilds BOTH sides, so this runs every two hours there and the weekly
-- `+tag:production` build keeps full authority. The narrow tag rather than `full_refresh_only`,
-- for the reason A105 established: the blunt one costs real coverage.
-- R-685. A SPREAD SHOWN BESIDE THE WRONG TEAM IS THE DEFECT MARC REPORTED.
--
-- Marc, 2026-09-12: "show the favorite with the negative spread." `spread` is home-perspective,
-- so rendering it beside the AWAY team without a sign flip shows the UNDERDOG carrying the
-- negative number — and it looks entirely plausible.
--
-- srv_game_team.spread_final already flips it: coalesce(spread_at_close, spread_current),
-- negated on the away row. This asserts that it still does, from BOTH sides at once, which is
-- the property a sign flip breaks and a single-sided test cannot see.
--
-- 🚨 AND IT IS THE SPREAD'S FAVOURITE, NOT THE MONEYLINE'S. Both definitions exist and
-- `favorite_definitions_disagree` exists because they differ on 70 games. The card shows a
-- SPREAD, so `spread_favorite_side` is the authority here; joining moneyline_favorite_side
-- instead would fail on those 70 for a reason that is not this one.
--
-- Zero is excluded rather than treated as an error: a pick'em has no favourite to name.
select
    t.game_id,
    t.team_id,
    t.is_home,
    m.spread_favorite_side,
    t.spread_final,
    case when t.is_home then 'home' else 'away' end as this_side,
    'the favourite must carry the negative number' as rule
from {{ ref('srv_game_team') }} t
join {{ ref('fct_game_market') }} m on m.game_id = t.game_id
where t.spread_final is not null
  and t.spread_final <> 0
  and m.spread_favorite_side is not null
  and (
        -- this team IS the favourite, so its spread must be negative
        (m.spread_favorite_side = case when t.is_home then 'home' else 'away' end
         and t.spread_final > 0)
        -- this team is NOT the favourite, so its spread must be positive
     or (m.spread_favorite_side <> case when t.is_home then 'home' else 'away' end
         and t.spread_final < 0)
      )
