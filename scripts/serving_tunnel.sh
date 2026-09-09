#!/usr/bin/env bash
# Open a READ path to the droplet's SERVING Postgres. Leave it running.
#
#     scripts/serving_tunnel.sh            # silence is success — ^C to close
#
# This is the sibling of scripts/warehouse_tunnel.sh and the same boundary applies: it
# forwards one port and runs no remote command. It cannot publish and cannot deploy.
#
# WHY IT IS SIMPLER THAN THE WAREHOUSE ONE. The warehouse publishes no host port, so that
# script has to resolve a container IP that Docker reassigns. Serving DOES listen on the
# droplet's loopback at 5433, so the address is stable and there is nothing to discover.
#
# The far end is 5433 ON THE DROPLET; the near end is yours. They are different numbers on
# purpose — 15434 locally, so a laptop that also runs a Postgres cannot silently answer for
# production, which is the failure the retired CFDB_DROPLET_PG_ADDR produced.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

[ -f .env ] && { set -a; . ./.env; set +a; }
: "${CFDB_DROPLET_HOST:?CFDB_DROPLET_HOST is not set — add it to .env (see .env.example)}"

LOCAL_PORT="${SERVING_PG_PORT:-${CFDB_PUBLISHED_PORT:-15434}}"
REMOTE_PORT=5433

if [ "$LOCAL_PORT" = "5432" ]; then
  echo "error: local port 5432 is the database that was dropped on 2026-09-05 (R-296)." >&2
  echo "       Pick another — 15434 is the convention for serving." >&2
  exit 1
fi

echo "forwarding: 127.0.0.1:${LOCAL_PORT} -> 127.0.0.1:${REMOTE_PORT} on ${CFDB_DROPLET_HOST#*@}"
echo "then, in another terminal:"
echo "    python scripts/verify_read_credential.py"
echo "(silence below is success — ^C to close)"

exec ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" "$CFDB_DROPLET_HOST"
