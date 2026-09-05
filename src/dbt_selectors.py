"""dbt selector fragments shared by the DAGs.

WHY THIS MODULE EXISTS (R-337).

`--exclude tag:full_refresh_only tag:slow_sweep` lived as a string literal in
scores_refresh_dag.py and nowhere else. cfbd_lines_snapshot runs the same shape of job — a
`dbt run` over a narrow selector, then `dbt test` over that same selector — and never got the
flag. From 2026-09-04 08:00 to 2026-09-05 that DAG failed every four-hourly run on
`assert_games_played_reconciles_to_schedule`, and `publish_distributions` did not run once.

The test was not wrong and the data was not bad. `stg_games` is in the distribution selector
and `mart_team_season_record` is in neither selector, so every run advanced the schedule side
of that assertion and never the mart side. The gap grew from 108 team-games to 216 in a day.

Two copies of a rule in two files is how the two diverged, so there is now one copy and both
DAGs import it. A third DAG that forgets it fails
tests/test_dag_structure.py::test_every_partial_rebuild_dag_excludes_the_full_refresh_tags,
which discovers the DAGs rather than naming them.

THE RULE, so the next author understands it rather than copying a flag:

    A PARTIAL-REBUILD DAG MUST NOT ASSERT A FULL-REFRESH INVARIANT.

A job that rebuilds part of the graph and then tests that part will sweep up tests whose
relations straddle the edge of its selector. Those tests compare something it just rebuilt
against something it did not, so they report the refresh boundary as a data defect. They are
correct assertions; this is simply not the job that can satisfy them. The weekly DAGs rebuild
the whole production set and are where those tests have their authority.

TWO TAGS, TWO REASONS, AND THEY ARE NOT INTERCHANGEABLE.

  full_refresh_only  the DAG CANNOT satisfy the test — it straddles the refresh boundary and
                     would report a gap between two fetch times as a failure.
  slow_sweep         the DAG CAN satisfy it, but the test costs minutes and re-checks a
                     property that only changes when a model changes. Excluded to keep the
                     frequent jobs cheap, which is the whole reason they can be frequent.

Kept apart so the first tag's meaning stays enforceable:
test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags asserts nothing wears
it without straddling the boundary, and that check is only worth having while the tag means
one thing.
"""

# The exclusion every partial-rebuild DAG applies to its `dbt test`. NOT applied by the
# weekly DAGs: they rebuild both sides of these assertions, which is what gives the tagged
# tests somewhere to run. See docstring above before changing either fact.
PARTIAL_REBUILD_TEST_EXCLUDE = "--exclude tag:full_refresh_only tag:slow_sweep"
