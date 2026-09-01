-- Every team-scoped statistic must have an opponent-scoped twin, and vice versa.
--
-- fct_team_season_stat derives `stat_scope` and `stat_base_name` from CFBD's `Opponent`
-- suffix. That derivation is only safe while the convention holds, and the Stats page was
-- right to refuse to do it in the app: "it would be wrong the first time CFBD names
-- something differently."
--
-- This is what makes doing it in the warehouse different from doing it in the page. The rule
-- is not assumed, it is asserted: if CFBD ships `firstDownsAllowed` instead of
-- `firstDownsOpponent`, or drops an opponent variant, the pairing breaks here and the build
-- says so — rather than the Stats page silently offering a scope filter that hides half a
-- statistic.
--
-- `games` is excluded by name and only by name. It is a count of fixtures rather than a
-- performance measure, so an opponent variant of it would be meaningless — a team and its
-- opponents play the same number of games. Excluding it by an explicit name rather than by a
-- pattern keeps the exemption to exactly one stat.
with scoped as (
    select distinct stat_base_name, stat_scope
    from {{ ref('fct_team_season_stat') }}
    where stat_name <> 'games'
),
paired as (
    select
        stat_base_name,
        max(case when stat_scope = 'team' then 1 else 0 end)     as has_team,
        max(case when stat_scope = 'opponent' then 1 else 0 end) as has_opponent
    from scoped
    group by stat_base_name
)
select stat_base_name, has_team, has_opponent
from paired
where has_team = 0 or has_opponent = 0
