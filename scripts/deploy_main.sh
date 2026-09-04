#!/usr/bin/env bash
# Deploy origin/main to production. One command, one meaning.
#
# WHY THIS WAS REWRITTEN. "Deployed" used to mean three different things: the Airflow DAGs
# came from a git worktree on the laptop, the droplet's site was a file copy with no git at
# all, and the forced command was an scp. Merging to main updated exactly one of them. That
# gap cost a day of site downtime on 30 August — the cache-TTL fix was on main and not on the
# droplet, and a diff that compared only the files present in both places reported "no
# difference" while two files existed on one side alone.
#
# Since the migration, production is the droplet and nothing else. This script deploys BOTH
# halves that live there and verifies each one, because the site and the pipeline are
# separate images with separate failure modes.
#
# THE LAPTOP STACK IS NOT TOUCHED. It is paused as the M3 rollback and decommissioned when
# M3 closes (decision log 2026-08-31). Refreshing it here would quietly recreate the
# two-productions problem this script exists to end.
#
#   scripts/deploy_main.sh              pipeline + site, only what changed
#   scripts/deploy_main.sh --site-only  skip the pipeline
#   scripts/deploy_main.sh --force-site rebuild the site image even if unchanged
#   scripts/deploy_main.sh --rebuild    rebuild and publish EVERY production model
#
# ==========================================================================================
# WHAT CHANGED ON 2026-09-04, AND THE MEASUREMENTS BEHIND IT
#
# 1. IT DID NOT DEPLOY origin/main. The pipeline half reset the droplet's checkout to
#    origin/main; the site half tarred up the LOCAL WORKING DIRECTORY. Deploying from a
#    feature branch therefore put un-merged code on the live site — which happened, for about
#    twenty minutes, on the day this was found. The site now comes from `git archive
#    origin/main:site`, so the branch you happen to have checked out cannot reach production.
#
# 2. IT REBUILT 95 MODELS TO SHIP ONE. Any change under dbt/models/serving/ triggered
#    `dbt run --select +tag:production`: 328 seconds, measured. Rebuilding the model that
#    actually changed plus its children takes 18. `src/deploy_models.py` now selects with
#    `state:modified+` against the manifest from the last successful deploy — which is also
#    STRICTER, because the old directory diff could not see an upstream mart or macro change
#    and its own comment said so.
#
# 3. IT PUBLISHED THE WHOLE HOT SERVING SET whatever had been rebuilt. Now it publishes the
#    tables dbt reports it actually built, and nothing else.
#
# 4. IT OPENED A DOZEN SSH CONNECTIONS. One, multiplexed, reused by both halves.
#
# 5. THE TWO HALVES RAN IN SERIES though they touch nothing in common. The site now builds
#    while the warehouse rebuilds, and both results are reported.
#
# 6. IT SLEPT TWELVE SECONDS and hoped. It polls for health.
#
# The order matters: (1) is what makes (2) safe to do. Rebuilding "only what changed" is
# worth nothing if you cannot say which commit "changed" is measured against.
# ==========================================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

fail() { echo "::error::$*" >&2; exit 1; }

# The host is configuration, never a literal in a tracked file.
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${SERVING_SSH_HOST:?SERVING_SSH_HOST is not set — add it to .env (root@<droplet ip>)}"
# ONE TCP CONNECTION, REUSED. The script makes a dozen calls and each used to pay a full
# handshake; both halves now share this socket, which is also what makes running them
# concurrently cheap rather than twice the setup.
SSH_SOCKET="${TMPDIR:-/tmp}/cfdb-deploy-$$.sock"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=25
          -o ControlMaster=auto -o ControlPath="$SSH_SOCKET" -o ControlPersist=180)
SSH=(ssh "${SSH_OPTS[@]}" "$SERVING_SSH_HOST")
# Closed on the way out however we leave, so a killed deploy does not strand a master.
trap 'ssh -O exit -o ControlPath="$SSH_SOCKET" "$SERVING_SSH_HOST" >/dev/null 2>&1 || true' EXIT
# OPENED ONCE, BEFORE THE TWO HALVES FORK. Without this they race to create the master and
# the loser prints "ControlSocket already exists, disabling multiplexing" and pays for its own
# connection — the multiplexing silently does not happen for half the deploy.
"${SSH[@]}" true >/dev/null 2>&1 || fail "cannot reach $SERVING_SSH_HOST over ssh"

PIPELINE_DIR=/opt/cfdb-pipeline
SITE_DIR=/opt/cfdb/site
DO_PIPELINE=1
FORCE_SITE=0
FORCE_REBUILD=0
REBUILD_FLAG=""
for arg in "$@"; do
  case "$arg" in
    --site-only)  DO_PIPELINE=0 ;;
    --force-site) FORCE_SITE=1 ;;
    --rebuild)    FORCE_REBUILD=1; REBUILD_FLAG=" --full" ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done


echo "Deploying origin/main to ${SERVING_SSH_HOST#*@}"
git fetch origin main --quiet
echo "  local origin/main: $(git rev-parse --short origin/main)"
# SAID OUT LOUD, because it used not to be true. Nothing below reads the working tree any
# more, so a feature branch is harmless — but "I deployed and my change is not there" is a
# confusing ten minutes, and one line prevents it.
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "  note: you are on $(git rev-parse --abbrev-ref HEAD); only origin/main is deployed"
fi

# ---------------------------------------------------------------- pipeline ---
pipeline_half() {
  echo "[pipeline] $PIPELINE_DIR/repo"
  local before after errors
  before=$("${SSH[@]}" "git -C $PIPELINE_DIR/repo rev-parse --short HEAD")
  "${SSH[@]}" "git -C $PIPELINE_DIR/repo fetch --quiet origin && \
               git -C $PIPELINE_DIR/repo reset --hard --quiet origin/main"
  after=$("${SSH[@]}" "git -C $PIPELINE_DIR/repo rev-parse --short HEAD")
  if [ "$before" = "$after" ]; then
    echo "  already at $after"
  else
    echo "  $before -> $after"
    "${SSH[@]}" "git -C $PIPELINE_DIR/repo log --oneline $before..$after" | sed 's/^/    /'
  fi

  # R-126 / R-264. A MODEL CHANGE IS NOT DEPLOYED UNTIL THE DATA IS REBUILT.
  #
  # Moving the pipeline repo to main updates the SQL; it does not run it. The scores DAG that
  # would normally rebuild and publish is gated on the live-scoring window, so outside one
  # every run correctly succeeds having done nothing — and a serving-model change merged on a
  # Tuesday reaches the site on Saturday. That is not theoretical: on 2 September the site
  # asked srv_game for three columns the published table did not have, and Schedule rendered
  # "Something went wrong reading srv_game" until this was done by hand.
  #
  # WHAT DECIDES, AND WHY IT MOVED OUT OF THIS SCRIPT. It used to be a directory diff over
  # dbt/models/serving/, which was both too slow and too narrow — it rebuilt all 95 production
  # models for a one-model change (328s against 18s, measured) and it could not see an
  # upstream mart or macro change at all. `src/deploy_models.py` compares against the manifest
  # from the last successful deploy instead. Real logic belongs somewhere it can be tested,
  # not shell-quoted through ssh into docker exec.
  #
  # It is always run: deciding there is nothing to do takes about a second, and the decision
  # is the part that has to be right.
  echo "  reconciling models with origin/main..."
  "${SSH[@]}" "cd $PIPELINE_DIR && docker compose exec -T airflow-scheduler bash -lc \
    'cd /opt/airflow/project && python -m src.deploy_models$REBUILD_FLAG'" \
    || fail "model rebuild/publish failed"

  # DAGs are read from disk, so no restart is needed for a DAG change. An import error is
  # the thing worth surfacing immediately — a DAG that will not parse is a DAG that silently
  # stops being scheduled.
  echo "  checking DAG imports..."
  errors=$("${SSH[@]}" "cd $PIPELINE_DIR && docker compose exec -T airflow-scheduler \
             airflow dags list-import-errors 2>/dev/null | grep -v masking | tail -5" || true)
  case "$errors" in
    *"No data found"*|"") echo "    no import errors" ;;
    *) echo "$errors" | sed 's/^/    /'; fail "DAG import errors after deploy" ;;
  esac
}

# -------------------------------------------------------------------- site ---
# FROM origin/main, NOT FROM THE WORKING DIRECTORY — the defect this rewrite exists for. The
# old version ran `tar czf - -C site .` over whatever was checked out, so deploying from a
# feature branch put un-merged code on the live site. `git archive` reads the commit.
#
# THE TREE HASH IS THE CHANGE GUARD. `git rev-parse origin/main:site` is git's own hash of
# that directory's contents at that commit — exact, one word, and free. The previous guard
# hashed every file on both sides with two different tools and compared the digests, which
# worked but could only ever answer "the same as my laptop right now".
#
# The marker is written only after the smoke test passes, so a deploy that failed halfway is
# retried rather than skipped. It lives OUTSIDE $SITE_DIR because that directory is a Docker
# build context and gets replaced wholesale below.
site_half() {
  echo "[site] $SITE_DIR"
  local wanted current
  wanted=$(git rev-parse "origin/main:site")
  current=$("${SSH[@]}" "cat /opt/cfdb/.deployed-site-tree 2>/dev/null" || echo none)

  if [ "$wanted" = "$current" ] && [ "$FORCE_SITE" = 0 ]; then
    echo "  unchanged at ${wanted:0:12}, not rebuilding"
  else
    echo "  syncing site/ at ${wanted:0:12} ..."
    # EXTRACT BESIDE, THEN SWAP. Untarring over the top only ever adds and overwrites, so a
    # file deleted on main lingered on the droplet forever and could still be imported. A
    # fresh directory makes the deployed tree exactly the commit's tree.
    "${SSH[@]}" "rm -rf $SITE_DIR.new && mkdir -p $SITE_DIR.new"
    git archive --format=tar "origin/main:site" \
      | "${SSH[@]}" "tar xf - -C $SITE_DIR.new"
    "${SSH[@]}" "rm -rf $SITE_DIR.old && mv $SITE_DIR $SITE_DIR.old 2>/dev/null; \
                 mv $SITE_DIR.new $SITE_DIR && rm -rf $SITE_DIR.old"
    echo "  rebuilding image..."
    "${SSH[@]}" "cd /opt/cfdb && docker compose build site >/dev/null 2>&1 && \
                 docker compose up -d site >/dev/null 2>&1"
  fi

  # POLLED, NOT SLEPT. Twelve seconds was a guess that was too long on a no-op and would be
  # too short the day the image got heavier — the failure mode of the second is a red deploy
  # for a site that was merely still starting.
  echo "  waiting for health..."
  local health="" i
  for i in $(seq 1 30); do
    health=$("${SSH[@]}" "cd /opt/cfdb && docker compose exec -T site python -c \
      \"import urllib.request;print(urllib.request.urlopen('http://localhost:8501/_stcore/health',timeout=5).read().decode())\" \
      2>/dev/null" || true)
    case "$health" in ok*) break ;; esac
    sleep 2
  done
  echo "    health: ${health:-unreachable}"
  case "$health" in ok*) ;; *) fail "site did not report healthy" ;; esac

  # THE SITE IS NOT DEPLOYED UNTIL IT RENDERS. "The data is correct" and "the site works" are
  # different claims (CLAUDE.md, 2026-08-31); this checks the second one.
  echo "  verifying..."
  scp -q "${SSH_OPTS[@]}" ci/site_smoke.py "$SERVING_SSH_HOST:/tmp/site_smoke.py"
  local smoke
  smoke=$("${SSH[@]}" "cd /opt/cfdb && docker compose cp /tmp/site_smoke.py site:/app/site_smoke.py \
            >/dev/null 2>&1 && docker compose exec -T site python /app/site_smoke.py 2>&1 \
            | grep -E '^OK|^FAIL'" || true)
  echo "    ${smoke:-no output from the smoke test}"
  case "$smoke" in OK*) ;; *) fail "site smoke test did not pass" ;; esac

  # Recorded last, so a half-finished deploy is retried rather than believed.
  "${SSH[@]}" "printf %s $wanted > /opt/cfdb/.deployed-site-tree"
}

# THE MONITOR'S FORCED COMMAND SHIPS WITH THE DEPLOY, because it did not and drifted.
#
# `deploy/cfdb_heartbeat.sh` is what the GitHub watcher runs over SSH, and it was installed by
# hand. On 2026-09-04 the checker learned to read failure lines and the droplet's copy did not
# have them for another hour — the monitor reported a clean pipeline while two DAGs were
# failing, which is the exact silence the change was meant to end.
sync_monitor() {
  [[ -f deploy/cfdb_heartbeat.sh ]] || return 0
  echo "[monitor] syncing the forced command..."
  scp -q "${SSH_OPTS[@]}" deploy/cfdb_heartbeat.sh \
      "$SERVING_SSH_HOST:/usr/local/bin/cfdb_heartbeat.sh"
  "${SSH[@]}" 'chown root:root /usr/local/bin/cfdb_heartbeat.sh && \
               chmod 0755 /usr/local/bin/cfdb_heartbeat.sh'
}

# THE TWO HALVES TOUCH NOTHING IN COMMON, so they run together. The site's image build and the
# warehouse's rebuild are minutes of independent work that used to be added rather than
# overlapped.
#
# The site half writes to a log instead of the terminal: two concurrent streams interleaved
# line by line is a deploy nobody can read, and worse, a failure nobody can attribute. Both
# exit codes are collected and BOTH are reported — a green pipeline must not hide a red site.
SITE_LOG="${TMPDIR:-/tmp}/cfdb-deploy-site-$$.log"
site_rc=0
pipeline_rc=0
echo
site_half >"$SITE_LOG" 2>&1 &
site_pid=$!

if [ "$DO_PIPELINE" = 1 ]; then
  pipeline_half || pipeline_rc=$?
fi
sync_monitor || true

wait "$site_pid" || site_rc=$?
cat "$SITE_LOG"
rm -f "$SITE_LOG"

[ "$pipeline_rc" = 0 ] || fail "the pipeline half failed (exit $pipeline_rc)"
[ "$site_rc" = 0 ] || fail "the site half failed (exit $site_rc)"

echo
echo "Deployed."
