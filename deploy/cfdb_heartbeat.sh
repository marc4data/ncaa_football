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
# Six hours because the two-hourly DAG retries for roughly thirty minutes: a window shorter
# than a few runs would let a failure scroll out of view between watcher runs, which are
# themselves four hours apart in practice.
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
  select 'failed|' || dag_id || '.' || task_id || '|' ||
         floor(extract(epoch from (now() - end_date)))::bigint
  from (
    select dag_id, task_id, state, end_date,
           row_number() over (partition by dag_id, task_id
                              order by end_date desc) as recency
    from task_instance
    where end_date > now() - interval '6 hours'
      and state in ('failed', 'success')
  ) ranked
  where recency = 1 and state = 'failed'
  order by dag_id, task_id
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
