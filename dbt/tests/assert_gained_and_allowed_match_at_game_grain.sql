{{ config(severity='error', tags=['full_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` for its sibling's reason (R-672): it compares marts the two-hourly
-- scores DAG does not rebuild on one cadence, and `ci/check_test_refresh_scope.py` would otherwise
-- stop that DAG's publish.
--
-- MARC'S INVARIANT, AS AN ASSERTION. A142, cfdb-main-R-962. His words, 2026-09-16:
--
--     "Why are the box whiskers min, 25th, 50th, 75th, and max different between the Gained Team
--      and the Allowed team.  If Oregon gained 497 yards last week. the opponent would have
--      Allowed 497 and the match for setting the min/max and quartiles would lead to the same
--      results."
--
-- ✅ HE IS RIGHT AT THIS GRAIN AND IT IS AN EXACT IDENTITY. The pool is a set P of team-games;
-- `mirror` sends a team-game to the other side of the same fixture and is a BIJECTION on P as long
-- as P is closed. So {value(x) : x in P} and {value(mirror(x)) : x in P} are the same multiset —
-- every percentile, the mean, the whiskers, the count. ⚠️ NULLS AND MISSING BOX SCORES DO NOT
-- WEAKEN IT: closure is necessary and sufficient, and nothing about the VALUES enters the argument.
--
-- 🚨 AND IT IS FALSE ONE MODEL OVER, WHICH IS WHY THE CLAIM IS PINNED TO THIS GRAIN AND NOT TO THE
-- PROJECT. `fct_team_week_metric_distribution` holds season-to-date AVERAGES, and averaging
-- destroys the pairing. Measured over a PERFECTLY CLOSED league (2025 regular, FBS-vs-FBS only,
-- 762 games, sum_for = sum_allowed = 574,631): at game grain gained and allowed agree to the digit
-- at 302.75 / 377.5 / 448.0, and at team-average grain they read 333.1 / 383.3 / 410.2 against
-- 346.5 / 384.6 / 415.1 — even the grand means differ, because teams had played 11, 12 or 13 games.
-- Design note 6 in that model carries the table. ❌ DO NOT COPY THIS TEST THERE; it would be red
-- for a reason no edit can fix.
--
-- ⚠️ cfdb-wta-R-944: A TEST MUST NOT KEY ON A VALUE THE DEFECT CONTROLS. The defect this guards
-- against is a pool that has lost mirrors, so the allowed side is built by JOINING each team-game
-- to its mirror — an inner join. A lost mirror silently removes that row from the allowed side and
-- the counts and percentiles diverge from the published gained ones. ✅ The assertion is therefore
-- keyed on the PUBLISHED distribution against an INDEPENDENTLY DERIVED opponent distribution, and
-- on neither the population rule read back nor anything the pool itself reports about its size.
--
-- ⚠️ R-760: what would have to be wrong for this to fire? Any per-team join returning to the
-- population (a `dim_team` inner join drops the 52–62 completed team-games a season that carry no
-- dim_team row and leaves their mirrors behind); an inner join to `fct_game_team_advanced`; a
-- filter on a one-sided column such as `has_box_score`. Each is a plausible one-line edit and each
-- reopens exactly the defect Marc saw.
--
-- `total_yards` DELIBERATELY, where the sibling population test uses `rushing_yards`: one metric
-- each, two metrics covered, and eighteen recomputations of a 2.7M-row table bought nothing.
with fbs_games as (

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
           t.total_yards
    from {{ ref('fct_game_team') }} t
    join fbs_games g
      on g.game_id = t.game_id
    where t.is_completed

),

allowed as (

    -- THE ALLOWED DISTRIBUTION, BUILT BY REACHING ACROSS THE FIXTURE. `o` is the other side of
    -- `p`'s own game, so `o.total_yards` is what `p` conceded. One grouped pass, joined — not a
    -- correlated subquery per row (A097: 0.9s against 65.5s on this family of models).
    select
        p.season, p.season_type, p.week,
        percentile_cont(0.25) within group (order by o.total_yards) as p25,
        percentile_cont(0.50) within group (order by o.total_yards) as p50,
        percentile_cont(0.75) within group (order by o.total_yards) as p75,
        min(o.total_yards)                                          as min_value,
        max(o.total_yards)                                          as max_value,
        count(o.total_yards)                                        as n
    from pool p
    join pool o
      on o.game_id = p.game_id and o.team_id = p.opponent_team_id
    group by p.season, p.season_type, p.week
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
    'gained and allowed describe the same closed set of team-games, so every figure must match'
        as rule
from {{ ref('fct_game_team_metric_distribution') }} g
join allowed a
  on  a.season = g.season and a.season_type = g.season_type and a.week = g.week
where g.metric = 'total_yards'
  and (g.n         is distinct from a.n
    or g.p25       is distinct from a.p25
    or g.p50       is distinct from a.p50
    or g.p75       is distinct from a.p75
    or g.min_value is distinct from a.min_value
    or g.max_value is distinct from a.max_value)
