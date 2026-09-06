#!/usr/bin/env bash
# Open a read/build path to the droplet's WAREHOUSE Postgres. Leave it running.
#
#     scripts/warehouse_tunnel.sh          # prints nothing when it works; -N means no
#                                          # remote command, so a silent terminal is success
#
# ==========================================================================================
# THIS IS NOT A DEPLOY PATH, AND THE DIFFERENCE IS THE POINT.
#
# deploy/README.md deliberately stopped documenting the individual rsync and docker commands:
# "someone running them by hand is someone deploying half of production without verifying
# it." That judgement stands and this script does not reopen it.
#
# What this opens is a READ AND BUILD path to the transform warehouse — the database dbt
# builds into, which nothing user-facing reads. The site reads the SERVING Postgres, a
# different instance, and the only thing that writes to it is src/publish_marts.py over a
# forced-command SSH identity. This script cannot reach it, cannot publish, and cannot
# deploy: it forwards one port to one database and runs no remote command at all.
#
# The boundary is therefore structural rather than a promise. If you want to change what the
# site shows, that is still scripts/deploy_main.sh, and it is still the only way.
# ==========================================================================================
#
# WHY THE ADDRESS IS RESOLVED HERE RATHER THAN STORED
#
# The retired CFDB_DROPLET_PG_ADDR stored the warehouse container's Docker IP (172.19.0.2)
# in .env, which fails in the worst available way: Docker reassigns it whenever the stack is
# recreated, and the tunnel then opens SUCCESSFULLY against nothing, or against whatever now
# holds the address. It does not error; it answers.
#
# TWO PATHS, AND AS OF 2026-09-05 ONLY THE SECOND ONE FIRES:
#
#   1. 127.0.0.1:5432 ON THE DROPLET. Kept as a probe, but it does NOT trigger today and is
#      not expected to: A051 measured the pipeline stack and the warehouse PUBLISHES NO HOST
#      PORT AT ALL. The root docker-compose.yml's `5432:5432` is not what production runs
#      (see the header of that file). This path becomes live only when the compose
#      reconciliation lands together with `env/warehouse-loopback-bind`.
#   2. THE CONTAINER IP, RESOLVED NOW. This is the working path, every time.
#
# Path 1 earns its keep as a MEASUREMENT rather than a shortcut: it failing is one of the two
# independent confirmations that the warehouse publishes nothing, the other being the running
# compose file's own comment. Leave it in.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
fail() { echo "error: $*" >&2; exit 1; }

[ -f .env ] && { set -a; . ./.env; set +a; }
: "${CFDB_DROPLET_HOST:?CFDB_DROPLET_HOST is not set — add it to .env (see .env.example)}"

LOCAL_PORT="${CFDB_WAREHOUSE_PORT:-${CFDB_REMOTE_PG_PORT:-15433}}"
[ "$LOCAL_PORT" = "5432" ] && fail "local port 5432 is the database that was dropped on
  2026-09-05 (R-296), and scripts/preflight_env.py refuses it on purpose. Pick another —
  15433 is the convention. See CLAUDE.md, \"Environments\"."

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20)

# WHICH CONTAINER IS THE WAREHOUSE — ASKED, NOT ASSUMED, AND NOW ANSWERED.
#
# Path 2 resolves by COMPOSE LABEL rather than by container name. The name was in doubt when
# this was written; A051 settled it, and the answer is the uncomfortable one:
#
#   the droplet runs a compose file THAT IS NOT IN GIT — one hand-merged
#   /opt/cfdb-pipeline/docker-compose.yml naming the service `warehouse`, where this repo
#   names it `postgres`. Container: cfdb-pipeline-warehouse-1.
#
# So the label filter is not belt-and-braces, it is the only thing here that is correct: a
# lookup by service name would have to pick one of the two spellings and would be wrong on
# the droplet. It also PRINTS WHAT IT FOUND on every run, which is how the divergence stays
# visible instead of being rediscovered. See CLAUDE.md, "Environments".
probe=$(ssh "${SSH_OPTS[@]}" "$CFDB_DROPLET_HOST" '
  # Path 1: is the warehouse already on the droplet loopback?
  if (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then echo "LOOPBACK 127.0.0.1"; fi
  # Path 2: whatever the pipeline project calls its Postgres.
  for id in $(docker ps -q --filter "label=com.docker.compose.project=cfdb-pipeline"); do
    docker inspect -f "CONTAINER {{.Name}} {{.Config.Image}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" "$id"
  done
' 2>/dev/null) || fail "cannot reach $CFDB_DROPLET_HOST over ssh"

echo "--- what the droplet reports ---"
echo "${probe:-(nothing)}" | sed "s/^/  /"
echo "--------------------------------"

if echo "$probe" | grep -q "^LOOPBACK"; then
  NAME="droplet loopback (docker-compose.yml)"; ADDR="127.0.0.1"
else
  line=$(echo "$probe" | grep -i "^CONTAINER" | grep -i postgres | head -1)
  [ -n "$line" ] || fail "no Postgres found in the droplet's cfdb-pipeline compose project,
  and nothing is listening on its 127.0.0.1:5432. Check the stack is up:
      ssh \$CFDB_DROPLET_HOST 'cd /opt/cfdb-pipeline && docker compose ps'"
  NAME=$(echo "$line" | awk '{print $2}' | sed "s#^/##")
  ADDR=$(echo "$line" | awk '{print $4}')
  echo "note: reached by container IP — the expected path today. The warehouse publishes no"
  echo "      host port, and this address is reassigned whenever the stack is recreated, so"
  echo "      it is resolved fresh each time and never stored. A stable loopback end arrives"
  echo "      with the compose reconciliation (env/warehouse-loopback-bind), not before."
fi

echo "warehouse : ${NAME} @ ${ADDR}:5432  (resolved just now, not stored)"
echo "forwarding: 127.0.0.1:${LOCAL_PORT} -> ${ADDR}:5432 via ${CFDB_DROPLET_HOST#*@}"
echo "set CFDB_WAREHOUSE_HOST=127.0.0.1 and CFDB_WAREHOUSE_PORT=${LOCAL_PORT} in .env, then:"
echo "    python scripts/preflight_env.py"
echo "(silence below is success — ^C to close)"

exec ssh -N "${SSH_OPTS[@]}" -L "${LOCAL_PORT}:${ADDR}:5432" "$CFDB_DROPLET_HOST"
