#!/usr/bin/env bash
#
# The ONLY thing the monitoring key can do on the droplet: report heartbeat ages.
#
# Installed at /usr/local/bin/cfdb_heartbeat.sh, owned by root, mode 0755, named as a forced
# command in ~cfdb_monitor/.ssh/authorized_keys:
#
#   command="/usr/local/bin/cfdb_heartbeat.sh",no-pty,no-port-forwarding,
#   no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... github-heartbeat-monitor
#
# WHY A FORCED COMMAND AGAIN. The same reasoning as deploy/cfdb_publish.sh, applied to a
# weaker need: the monitor only has to READ four timestamps, so it gets a key that can do
# nothing else. This one is narrower still — no verbs, no arguments, no client input of any
# kind. SSH_ORIGINAL_COMMAND is ignored entirely rather than parsed, because there is nothing
# a caller could legitimately vary.
#
# WHY THE MONITOR LIVES OUTSIDE THE DROPLET AT ALL. That is the entire point of a dead-man's
# switch. The laptop stack was down 24-28 August and nothing noticed, because every check
# that could have noticed was running on the machine that was off. A monitor that shares
# fate with the thing it monitors is not a monitor.
#
# The warehouse is not published to the host — it listens only on the compose network — so
# this reaches it at the container address. That keeps the key away from Docker, which is
# root by any other name.
set -euo pipefail
umask 077

WAREHOUSE_HOST="${CFDB_WAREHOUSE_HOST:-172.19.0.2}"
WAREHOUSE_PORT="${CFDB_WAREHOUSE_PORT:-5432}"

export PGCONNECT_TIMEOUT=10
PSQL=(psql -v ON_ERROR_STOP=1 -tA --no-psqlrc
      -h "$WAREHOUSE_HOST" -p "$WAREHOUSE_PORT"
      -U "${CFDB_PGUSER:-cfdb}" -d "${CFDB_PGDATABASE:-cfdb}")

# One line per cadence: name|seconds since the last beat. The caller decides what is stale,
# because the thresholds are cadence policy and belong in the monitor, not on the box being
# monitored — a box that is off cannot tell you its own thresholds changed.
"${PSQL[@]}" -c "
  select heartbeat_name || '|' ||
         floor(extract(epoch from (now() - max(beat_at))))::bigint
  from ops.pipeline_heartbeat
  group by heartbeat_name
  order by heartbeat_name
"

# AND RECENT FAILURES, BECAUSE ABSENCE IS TOO SLOW A SIGNAL ON A GAME DAY.
#
# A stale heartbeat eventually reveals a broken pipeline, but only after the threshold — five
# hours for the two-hourly DAG. On 2026-09-04 `dbt_test` began failing at 02:27 and the
# heartbeat did not cross its threshold until 05:07; the watcher's own cadence then delayed
# detection further. A failed task is knowable the moment it happens, and reporting it turns
# hours of silence into one watcher run.
#
# `failed|<dag>.<task>|<seconds ago>`, distinct from the heartbeat lines by its prefix so an
# older monitor that does not know about them simply ignores the lines it cannot parse.
#
# IF THE QUERY ITSELF CANNOT RUN, THAT IS REPORTED AS A FAILURE TOO. The first version echoed
# a differently-shaped line, which the watcher silently discarded as unparseable — so a
# monitor that had lost sight of failures looked exactly like a pipeline with none. That is
# the defect this whole change exists to remove, reintroduced one layer down. The monitor
# user needed `*` in the database field of its .pgpass to read the airflow metadata; without
# it this line is what says so.
#
# 🚨 A180 (cfdb-main-R-1861): THE WINDOW WAS SIX HOURS AND IT FORGOT A WEEKLY FAILURE.
#
# It used to read `interval '6 hours'`, and the reason given here was "the two-hourly DAG
# retries for roughly thirty minutes". That is correct for the two-hourly DAG and wrong for
# every slower one. A179 measured the cost: cfbd_results_refresh (WEEKLY, Sunday 12:00 UTC)
# failed on 2026-09-20 at 12:48:38 UTC, nothing ran after it, and the switch reported GREEN
# from 19:41 — fifty-three minutes after the failure left the window — on a pipeline whose
# load, dbt, publish and heartbeat were all sitting at `upstream_failed`.
#
# 📊 FIVE OF THE EIGHT SCHEDULED DAGs HAVE A CADENCE LONGER THAN SIX HOURS, not the three the
# incident suggested:
#
#     cfbd_scores_refresh     0 */2 * * *    every 2h   covered before
#     cfbd_lines_snapshot     0 */4 * * *    every 4h   covered before
#     cfbd_ops_metrics        0 13 * * *     daily      NOT covered
#     cfbd_databricks_sync    0 14 * * *     daily      NOT covered
#     cfbd_results_refresh    0 12 * * 0     weekly     NOT covered
#     cfbd_pregame_refresh    0 12 * * 2     weekly     NOT covered
#     cfbd_midweek_results    0 12 * * 4     weekly     NOT covered
#
# ✅ EIGHT DAYS: ONE WINDOW, SIZED TO THE SLOWEST CADENCE, NOT ONE PER DAG. A window per DAG
# would have to be declared by every DAG added afterwards, and a DAG that forgot to declare
# one would be this bug again — the alternative was considered and rejected for that reason.
# Eight covers the weekly seven with a day of slack, so a weekly failure stays reported right
# up to the run that would clear it.
#
# ⚠️ AND THE BOUND IS KEPT RATHER THAN REMOVED. Reporting the newest state for ALL TIME would
# match "nothing has shown it recovered" most literally, and it would also mean a task that
# was RENAMED while red stays on the alarm forever — an always-on alarm, which the paragraphs
# below call the same failure wearing the opposite mask. A finite window lets a task that no
# longer exists age out on its own.
#
# ⚠️ AND PAUSED OR DELETED DAGs ARE EXCLUDED, which the longer window makes necessary: over
# eight days a DAG can be paused or removed, and a failure from one nobody is running any more
# is noise. `is_stale` is Airflow's own marker for a DAG whose file is gone; the join to `dag`
# drops a deleted one outright.
#
# ONLY WHERE THE TASK'S MOST RECENT RUN FAILED — "has failed" is not "is failing".
#
# The first version reported any failure inside the window regardless of what happened after
# it, so a task that failed once and succeeded on the next run stayed red for six hours. On
# 2026-09-04 that put three tasks on the alarm at once, all three healthy: a distribution
# test fixed at 22:33, a scores dbt_test with eight successes behind it, and a build from
# fourteen hours earlier. The pipeline was fine and the switch said otherwise.
#
# THAT IS WORSE THAN A LATE ALARM, and this project has the entry to prove it. "Silence is
# not success" was added after four days of unnoticed downtime; an alarm that is always on is
# the same failure wearing the opposite mask, because the next real outage arrives on a board
# that is already red and changes nothing anybody looks at.
#
# `recency = 1` is the whole fix: rank each task's runs in the window newest first and report
# it only if the newest one failed. A task that failed five hours ago and has not run since
# is still reported, which is correct — nothing has shown it recovered.
"${PSQL[@]}" -d "${CFDB_AIRFLOW_DB:-airflow}" -c "
  select 'failed|' || ranked.dag_id || '.' || ranked.task_id || '|' ||
         floor(extract(epoch from (now() - ranked.end_date)))::bigint
  from (
    select dag_id, task_id, state, end_date,
           row_number() over (partition by dag_id, task_id
                              order by end_date desc) as recency
    from task_instance
    where end_date > now() - interval '8 days'
      and state in ('failed', 'success')
  ) ranked
  join dag on dag.dag_id = ranked.dag_id
  where ranked.recency = 1 and ranked.state = 'failed'
    and not dag.is_paused
    and not dag.is_stale
  order by ranked.dag_id, ranked.task_id
" || echo "failed|MONITOR.cannot_read_airflow_metadata|0"

# AND WHICH TEST, BECAUSE "dbt_test failed" HAS NEVER ONCE BEEN ENOUGH (R-412).
#
# The line above comes from Airflow's metadata database, which knows a task failed and
# structurally cannot know why -- it never sees dbt's run_results.json. Between 2026-09-04
# and 09-08 that produced five days of identical emails while the cause changed underneath
# them three times: a duplicated CFBD payload, then a test that could not see an append-only
# model. Each cost a full session to turn into one fact, and an alert that cannot tell those
# apart teaches its reader to stop opening it.
#
# WHERE THE JOIN HAPPENS, AND WHY HERE. The DAGs now run `capture_test_results` (all_done)
# which loads run_results.json into raw.raw_dbt_test_result. That table lives in THIS
# database, which this forced command already reads as this user for the heartbeat query
# above. So the payload costs no new privilege at all -- specifically NOT filesystem access
# to run_results.json, which would widen a forced command that is restricted on purpose.
#
# ── A182 (cfdb-main-R-1866): THE OUTCOME CHECK — ARE FINISHED GAMES ON THE SITE? ───────────
#
# > **MARC, 2026-09-20:** *"The data has to load and it has to be presented on the site. …
# > Saturday into Sunday is an unacceptable time to fail to load a full slate of game results.
# > Unacceptable."*
#
# 🚨 EVERY OTHER SIGNAL THIS SCRIPT EMITS MEASURES THE MACHINERY. The heartbeats say a cadence
# ran; the failure lines say a task broke; the test lines say an assertion fired. **Not one of
# them asks whether a reader can see last night's games** — which is why the 2026-09-19 slate
# was absent for more than a day while every check read green.
#
# 🚨 AND IT IS THE ONLY QUERY HERE THAT RUNS AGAINST **PUBLISHED SERVING** RATHER THAN THE
# WAREHOUSE. That distinction is the whole point: the warehouse having the data and the site
# showing it are different facts, and this project has confused them twice (R-878, and again
# in A179's first reading). The site reads the serving database, so the alarm must too.
#
# ⚠️ CURRENT SEASON ONLY, AND THAT IS A DELIBERATE BOUND. Box scores are `recent` scope, so
# 2023 and earlier legitimately have none and would put ~1,800 team-games on the alarm forever;
# and 2024 carries 8 team-games CFBD never produced an advanced box for. An always-on alarm is
# the same failure as a silent one — this file already argues that two hundred lines up — so
# the question is asked about the season being played.
#
# ⚠️ `> 3 hours` PAST THE GAME'S OWN DAY, not past kickoff: `srv_game_team.game_date` is a
# DATE, so the bound is "its day is over and three hours have passed", which is comfortably
# after the latest west-coast final and before the next morning.
#
# ✅ IT DEGRADES LOUDLY, like the airflow query above. If serving cannot be read, the line says
# so rather than the check silently reporting nothing wrong.
SERVING_HOST="${CFDB_SERVING_HOST:-127.0.0.1}"
SERVING_PORT="${CFDB_SERVING_PORT:-5433}"
SERVING_PSQL=(psql -v ON_ERROR_STOP=1 -tA --no-psqlrc
      -h "$SERVING_HOST" -p "$SERVING_PORT"
      -U "${CFDB_SERVING_USER:-cfdb_read}" -d "${CFDB_SERVING_DB:-cfdb}")

# 🚨 THE DEFAULT IS `cfdb_read`, NOT `cfdb`, AND THAT IS THE POINT — A183 (cfdb-main-R-1872).
# A182 shipped this check and it could never have answered, because the monitor's `.pgpass`
# carries a warehouse line and nothing for serving: every run emitted
# `unboxed|MONITOR.cannot_read_published_serving|0|-` and `ci/check_heartbeats.py` reported BLIND.
#
# ⚠️ THE OBVIOUS FIX WAS THE WRONG ONE. Adding a `.pgpass` line for `cfdb` would have worked
# first time and handed the MONITORING user SUPERUSER on the database the site reads — to run one
# `count(*)`. An alarm must not be able to damage the thing it is watching.
#
# ✅ `cfdb_read` already existed and needed no new grant: measured on serving before relying on
# it — SELECT on all 35 tables in the schema, and INSERT/UPDATE/DELETE all false on
# `srv_game_team`. So this is a credential line and a default, not a new privilege.

"${SERVING_PSQL[@]}" -c "
  select 'unboxed|' || count(*) || '|' ||
         coalesce(max(floor(extract(epoch from (now() - (game_date + 1))))::bigint), 0) || '|' ||
         coalesce(string_agg(distinct 'w' || week, ',' order by 'w' || week), '-')
  from serving.srv_game_team
  where is_fbs_game
    and is_completed
    and points_for is not null
    and season = (select max(season) from serving.srv_game_team where is_completed)
    and game_date < (now() at time zone 'America/Los_Angeles')::date
    and (not has_box_score or not has_box_advanced)
  having count(*) > 0
" || echo "unboxed|MONITOR.cannot_read_published_serving|0|-"

# One line per failing test: name, how many rows failed, how long ago. Not the log.
# 6 hours matches the failure window above so the two signals describe the same period.
"${PSQL[@]}" -c "
  select 'failed_test|' ||
         split_part(unique_id, '.', 3) || '|' ||
         coalesce(failures, 0)::text || '|' ||
         floor(extract(epoch from (now() - generated_at)))::bigint
  from (
    select unique_id, failures, generated_at, status,
           row_number() over (partition by unique_id
                              order by generated_at desc) as recency
    from raw.raw_dbt_test_result
    where generated_at > now() - interval '6 hours'
  ) ranked
  where recency = 1 and status in ('fail', 'error')
  order by failures desc nulls last, unique_id
" || echo "failed_test|MONITOR.cannot_read_dbt_results|0|0"
