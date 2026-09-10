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

# 🚨 R-625. NOT `exec`, AND A TRAP — BECAUSE EVERY NORMAL TEARDOWN LOOKED LIKE A FAILURE.
#
# Under `exec` the script's exit status IS ssh's, and ssh ended by a signal exits 128+N — so
# closing the tunnel with ^C printed `exit 144` after work that had gone perfectly. Marc
# reported it in two back-to-back rounds; it was explained correctly both times and nothing
# was wrong either time. THAT IS THE PROBLEM: a closing message that looks like a failure and
# is not trains a reader to stop reading closing messages, which is the one habit a monitoring
# story cannot afford. A090 made the same argument about verify_read_credential.py (R-566).
#
# ⚠️ A TRAP, NOT A STATUS CHECK AFTER THE COMMAND, AND THE FIRST VERSION OF THIS FIX GOT IT
# WRONG. ^C goes to the whole foreground process GROUP: ssh dies and this shell receives the
# same SIGINT, so under `set -e` it terminates without running whatever line comes next. A
# `status=$?` after the ssh call is never reached on the exact path it was written for. The
# trap runs on the signal itself, which is the only thing that does.
#
# ⚠️ NOT SILENCED — NAMED. A signal is a teardown; anything else is a real ssh failure and
# keeps its status, because "could not connect" and "you pressed ^C" are different facts and
# collapsing them would trade one misleading message for another.
#
# 🚨 WHAT WAS MEASURED, AND WHAT WAS NOT. The EXIT CODE is measured: with the trap, a signalled
# teardown exits 0 where it previously exited 144, verified on both paths — a signal to this
# shell and a signal to the ssh child. The MESSAGE could not be demonstrated in a
# non-interactive harness: the trap provably runs (exit 0 rather than 130) but its `echo` did
# not reach a redirected stderr in any of four attempts. It is written for a real terminal and
# is the belt to the exit code's braces. ⚠️ Said plainly rather than claimed, because a comment
# asserting behaviour nobody demonstrated is the thing this project keeps finding.
trap 'echo "tunnel closed — this is the teardown, not a failure." >&2; exit 0' INT TERM

ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" "$CFDB_DROPLET_HOST" || status=$?
status=${status:-0}

# ssh can also end by a signal WITHOUT this shell getting one — killed by pid, or the far end
# going away. Same fact, same message.
if [ "$status" -gt 128 ]; then
  echo "tunnel closed by signal $((status - 128)) — this is the teardown, not a failure." >&2
  exit 0
fi
if [ "$status" -ne 0 ]; then
  echo "tunnel FAILED: ssh exited ${status} (this one is a real error)." >&2
fi
exit "$status"
