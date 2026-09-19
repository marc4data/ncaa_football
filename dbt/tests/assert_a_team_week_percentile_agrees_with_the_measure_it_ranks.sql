-- A177 (cfdb-main-R-1771). Inside one (season, season_type, week), a team with MORE yards
-- gained must not carry a LOWER gained-percentile, and a team allowing FEWER yards must not
-- carry a lower allowed-percentile.
--
-- 🚨 THE TWO PERCENTILES RUN IN OPPOSITE DIRECTIONS AND THAT IS THE WHOLE POINT OF THE TEST.
-- `total_yards_for_percentile` ascends with its measure; `total_yards_allowed_percentile`
-- DESCENDS with its measure, so that higher is better in both. Those are two different
-- `order by` clauses four lines apart, and copying one onto the other is the obvious edit that
-- would put the worst defence in the country at p99 — a number that is wrong and looks fine.
--
-- ⚠️ A NULL CHECK COULD NOT SEE THIS. Both columns would still be 100% populated and still
-- sit in [0, 1]; only the pairing with the measure is wrong. R-843's rule one level up: the
-- value has to MOVE the right way under the thing it claims to rank.
--
-- ⚠️ SELF-JOIN ON THE POPULATION, NOT ON EVERY ROW. Both columns are null outside the
-- population they were computed over (FBS, at least one counted game), so the join is scoped
-- to rows that carry one — comparing a null to a null would fire on nothing and prove nothing
-- (R-760).
select
    a.season, a.season_type, a.week,
    a.team_display                     as team_a,
    a.total_yards_for_per_game         as a_gained,
    a.total_yards_for_percentile       as a_gained_pctile,
    b.team_display                     as team_b,
    b.total_yards_for_per_game         as b_gained,
    b.total_yards_for_percentile       as b_gained_pctile,
    a.total_yards_allowed_per_game     as a_allowed,
    a.total_yards_allowed_percentile   as a_allowed_pctile,
    b.total_yards_allowed_per_game     as b_allowed,
    b.total_yards_allowed_percentile   as b_allowed_pctile
from {{ ref('srv_team_week') }} a
join {{ ref('srv_team_week') }} b
  on  b.season      = a.season
  and b.season_type = a.season_type
  and b.week        = a.week
  and b.team_id    <> a.team_id
where a.total_yards_for_percentile is not null
  and b.total_yards_for_percentile is not null
  and (
        -- more yards gained, yet ranked lower
        (a.total_yards_for_per_game > b.total_yards_for_per_game
         and a.total_yards_for_percentile < b.total_yards_for_percentile)
        -- fewer yards allowed, yet ranked lower
     or (a.total_yards_allowed_per_game < b.total_yards_allowed_per_game
         and a.total_yards_allowed_percentile < b.total_yards_allowed_percentile)
      )
