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
"${PSQL[@]}" -d "${CFDB_AIRFLOW_DB:-airflow}" -c "
  select 'failed|' || dag_id || '.' || task_id || '|' ||
         floor(extract(epoch from (now() - max(end_date))))::bigint
  from task_instance
  where state = 'failed'
    and end_date > now() - interval '6 hours'
  group by dag_id, task_id
  order by dag_id, task_id
" || echo "failed|MONITOR.cannot_read_airflow_metadata|0"
