"""The Airflow pool that serialises writes to the Postgres warehouse.

WHY THIS EXISTS (cfdb-main-R-4860).

🚨 **EVERY DAG CARRIES `max_active_runs=1`, WHICH SERIALISES EACH DAG AGAINST ITSELF AND NOTHING
AGAINST THE OTHERS.** Measured at `ad1af4d`: there is no `pool=` anywhere in `dags/`, and the only
pool Airflow holds is `default_pool` with 128 slots.

📊 **AND THEY REALLY DO COLLIDE — 320 overlapping warehouse-write task pairs in 30 days, 1,478
minutes of overlap**, dominated by `cfbd_lines_snapshot` × `cfbd_scores_refresh` (281 pairs), which
share the top of every fourth hour by construction. The weekly chains overlapped a two-hourly DAG
39 times in the same window.

🚨 **THAT IS WHAT STOPPED SUNDAY.** On 2026-10-04 `cfbd_results_refresh` failed seven assertions and
the publish was gated off; on 2026-10-05 the SAME chain, re-run by hand with `cfbd_scores_refresh`
paused, passed all seven and published. Same code, same data, one variable.

⚠️ **ONE SLOT, AND THE NAME LIVES HERE RATHER THAN IN EACH DAG (R-574).** Three DAG files and five
DAGs assign it; a second copy of the string is how two of them would come to disagree, which is
exactly what `src/dbt_selectors.py` was written after.

🚨 **A TASK ASSIGNED TO A POOL THAT DOES NOT EXIST DOES NOT RUN.** The pool must exist on the
droplet before any commit using this constant reaches `main`:

    airflow pools set warehouse_write 1 "One writer at a time against the Postgres warehouse"
"""

#: The pool every warehouse-writing dbt or publish task runs in.
WAREHOUSE_WRITE_POOL = "warehouse_write"

#: One slot. The whole point is that the second writer waits.
WAREHOUSE_WRITE_SLOTS = 1
