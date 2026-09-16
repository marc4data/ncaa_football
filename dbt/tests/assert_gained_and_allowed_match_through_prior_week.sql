{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for its family's reason (R-672).
--
-- MARC'S INVARIANT, CARRIED ACROSS THE CUMULATIVE WINDOW. A143, cfdb-main-R-973 — the twin of
-- `assert_gained_and_allowed_match_at_game_grain`, which A142 wrote for the single-week sibling.
--
-- His words, 2026-09-16, which started all of this:
--
--     "Why are the box whiskers min, 25th, 50th, 75th, and max different between the Gained Team
--      and the Allowed team.  If Oregon gained 497 yards last week. the opponent would have
--      Allowed 497 and the match for setting the min/max and quartiles would lead to the same
--      results."
--
-- ✅ HE WAS RIGHT, AND IT HAS NOW BEEN CONFIRMED THREE TIMES INDEPENDENTLY: A142 proved it on the
-- closed pool, B118 measured it on live published rows (2026 wk1 both 276.00/367.50/470.50; wk2
-- both 283.25/357.50/459.75; 2025 wk7 both 305.75/375.00/448.00), and this asserts it holds under
-- the window too.
--
-- ✅ WHY IT SHOULD HOLD BY CONSTRUCTION: A142 closed the pool, so `mirror` — the map from a
-- team-game to the other side of the same fixture — is a bijection on it. **A union of closed
-- weeks is still closed**, so restricting to weeks strictly before W leaves a bijection and the
-- multiset of allowed values IS the multiset of gained values. Every percentile, the mean, the
-- extremes, the count.
--
-- 🚨 WHICH IS EXACTLY WHY IT IS ASSERTED RATHER THAN REASONED. "It holds by construction" is a
-- claim about a query somebody may edit, and the WINDOW is the kind of edit that can quietly drop
-- one side of a pair — a join that reaches for the opponent's week rather than the team's would
-- look right and break this. §2.4: the reasoning above is an inference; this is the measurement.
--
-- ⚠️ cfdb-wta-R-944 — A TEST MUST NOT KEY ON A VALUE THE DEFECT CONTROLS. The allowed side is built
-- by INNER-joining each team-game to its mirror, so a lost mirror silently removes that row and the
-- counts and percentiles diverge from the published gained ones. The assertion is keyed on the
-- PUBLISHED distribution against an INDEPENDENTLY DERIVED opponent distribution — not on the
-- population rule read back, and not on anything the window reports about its own size.
--
-- ⚠️ R-768 — AND IT DOES NOT REPRODUCE THE MODEL'S OWN WINDOW TO CHECK IT. The boundary is the
-- sibling test's job (`assert_the_prior_week_distribution_excludes_its_own_week`); this one takes
-- whatever window the model actually used and asks whether it is SYMMETRIC. Two tests, two
-- properties, neither standing in for the other.
--
-- `total_yards` deliberately, matching the single-week twin so the two read as one rule.
with ordinals as (

    select distinct season, season_type, season_type_ordinal, week
    from {{ ref('dim_team_week') }}

),

fbs_games as (

    select t.game_id
    from {{ ref('fct_game_team') }} t
    left join {{ ref('dim_team') }} d
      on d.season = t.season and d.team_id = t.team_id
    where t.is_completed
    group by t.game_id
    having bool_or(d.classification = 'fbs')

),

pool as (

    select t.season, t.season_type, t.week, t.game_id, t.team_id, t.opponent_team_id,
           t.total_yards, o.season_type_ordinal
    from {{ ref('fct_game_team') }} t
    join fbs_games g
      on g.game_id = t.game_id
    join ordinals o
      on o.season = t.season and o.season_type = t.season_type and o.week = t.week
    where t.is_completed
      and t.total_yards is not null

),

allowed as (

    -- Every team-game in the window, replaced by what it CONCEDED: the other side of its own
    -- fixture. One grouped pass, joined — not a correlated subquery per row (A097: 0.9s against
    -- 65.5s on this family).
    select
        s.season, s.season_type, s.week,
        percentile_cont(0.25) within group (order by o.total_yards) as p25,
        percentile_cont(0.50) within group (order by o.total_yards) as p50,
        percentile_cont(0.75) within group (order by o.total_yards) as p75,
        min(o.total_yards)                                          as min_value,
        max(o.total_yards)                                          as max_value,
        count(o.total_yards)                                        as n
    from ordinals s
    join pool p
      on  p.season = s.season
     and (p.season_type_ordinal, p.week) < (s.season_type_ordinal, s.week)
    join pool o
      on o.game_id = p.game_id and o.team_id = p.opponent_team_id
    group by s.season, s.season_type, s.week
    having count(o.total_yards) > 1

)

select
    g.season, g.season_type, g.week,
    g.n         as gained_n,       a.n         as allowed_n,
    g.p25       as gained_p25,     a.p25       as allowed_p25,
    g.p50       as gained_p50,     a.p50       as allowed_p50,
    g.p75       as gained_p75,     a.p75       as allowed_p75,
    g.min_value as gained_min,     a.min_value as allowed_min,
    g.max_value as gained_max,     a.max_value as allowed_max,
    'the window holds a closed set of team-games, so gained and allowed must agree exactly' as rule
from {{ ref('fct_game_team_metric_distribution_through_prior_week') }} g
join allowed a
  on  a.season = g.season and a.season_type = g.season_type and a.week = g.week
where g.metric = 'total_yards'
  and (g.n         is distinct from a.n
    or g.p25       is distinct from a.p25
    or g.p50       is distinct from a.p50
    or g.p75       is distinct from a.p75
    or g.min_value is distinct from a.min_value
    or g.max_value is distinct from a.max_value)
