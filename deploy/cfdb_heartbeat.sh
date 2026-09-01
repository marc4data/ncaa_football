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
