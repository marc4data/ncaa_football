{{ config(tags=['scores_refresh_only']) }}
-- 🚨 TAGGED `full_refresh_only` AFTER IT STOPPED THE SITE PUBLISHING. R-672, 2026-09-11.
--
-- This compares `fct_team_record_week` against `fct_game`. ⚠️ `cfbd_lines_snapshot`'s
-- DISTRIBUTION_SELECTOR rebuilds `fct_game` and NOT `fct_team_record_week` — measured with
-- `dbt ls`: 1 and 0 — so between the two refreshes it reads a fresh game table against a
-- stale record table. At 16:02 UTC it returned 2 rows, failed twice, and
-- `publish_distributions` did not run for four hours on a Friday.
--
-- ✅ THE ASSERTION IS NOT WRONG AND THE DATA IS NOT BAD. It passes on a full refresh — proven
-- twice: the droplet's 20:17 UTC run went green immediately after A103's `--rebuild`
-- recomputed all 104 models, and the same selector passes on a laptop against the same
-- warehouse. What it cannot survive is being asked the question halfway through a partial
-- rebuild. ⚠️ Tagging a test whose DATA is wrong would be muting an alarm; this one is the
-- remedy the project already uses, and the weekly `+tag:production` build keeps full
-- authority over it.
--
-- 🚨 AND THE TAG IS `scores_refresh_only`, NOT `full_refresh_only`, BECAUSE A GUARD SAID SO.
--
-- The first fix used `full_refresh_only`, and
-- `test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags` went red:
-- "these are selected by the scores DAG and do not straddle the boundary, so the tag costs
-- real coverage." ⚠️ IT WAS RIGHT. `cfbd_scores_refresh` rebuilds BOTH sides — this test is
-- meaningful there and runs every two hours — and the blunt tag would have removed it from
-- that run as well, because PARTIAL_REBUILD_TEST_EXCLUDE is one exclusion shared by both
-- gated DAGs.
--
-- ✅ So the exclusion is per DAG now: `cfbd_lines_snapshot` also excludes
-- `tag:scores_refresh_only`, `cfbd_scores_refresh` does not, and the weekly build runs
-- everything. The incident is fixed and no coverage is lost. A guard catching the FIRST fix
-- is the guard working.
-- The record for week N must not contain week N's result. R-084.
--
-- THE SINGLE MOST LIKELY DEFECT IN THIS MODEL, and the one that looks right on every row
-- except the ones anyone checks. A running total framed `unbounded preceding and current row`
-- rather than `... and 1 preceding` produces a column that is wrong by exactly one game, on
-- every row, forever — and a Schedule page showing "9-2" beside the game that made it 9-2
-- reads perfectly plausibly.
--
-- Asserted structurally rather than against one team: for every row, the record leading into
-- the NEXT week must equal this row's record plus this week's actual results. If the current
-- week leaked into the running total, this identity breaks everywhere at once.
--
-- Bye weeks are included deliberately — a week with no game must carry the record forward
-- unchanged, which this identity also proves.
with weekly as (
    select
        r.season, r.team_id, r.season_type_ordinal, r.week,
        r.wins, r.losses, r.ties,
        coalesce(g.wins, 0)   as played_wins,
        coalesce(g.losses, 0) as played_losses,
        coalesce(g.ties, 0)   as played_ties,
        lead(r.wins)   over w as next_wins,
        lead(r.losses) over w as next_losses,
        lead(r.ties)   over w as next_ties
    from {{ ref('fct_team_record_week') }} r
    left join (
        select season, season_type, week, team_id,
               sum(case when won then 1 else 0 end)  as wins,
               sum(case when lost then 1 else 0 end) as losses,
               sum(case when tied then 1 else 0 end) as ties
        from (
            select season, season_type, week, home_team_id as team_id,
                   home_points > away_points as won, home_points < away_points as lost,
                   home_points = away_points as tied
            from {{ ref('fct_game') }}
            where is_completed and home_points is not null and away_points is not null
            union all
            select season, season_type, week, away_team_id,
                   away_points > home_points, away_points < home_points,
                   away_points = home_points
            from {{ ref('fct_game') }}
            where is_completed and home_points is not null and away_points is not null
        ) sides
        group by season, season_type, week, team_id
    ) g on g.season = r.season and g.season_type = r.season_type
       and g.week = r.week and g.team_id = r.team_id
    where r.has_completed_games
    window w as (partition by r.season, r.team_id
                 order by r.season_type_ordinal, r.week)
)
select season, team_id, week, wins, played_wins, next_wins, losses, played_losses, next_losses
from weekly
where next_wins is not null
  and (next_wins   <> wins   + played_wins
    or next_losses <> losses + played_losses
    or next_ties   <> ties   + played_ties)
