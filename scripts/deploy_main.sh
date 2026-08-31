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
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The host is configuration, never a literal in a tracked file.
[ -f .env ] && { set -a; . ./.env; set +a; }
: "${SERVING_SSH_HOST:?SERVING_SSH_HOST is not set — add it to .env (root@<droplet ip>)}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=25 "$SERVING_SSH_HOST")

PIPELINE_DIR=/opt/cfdb-pipeline
SITE_DIR=/opt/cfdb/site
DO_PIPELINE=1
FORCE_SITE=0
for arg in "$@"; do
  case "$arg" in
    --site-only)  DO_PIPELINE=0 ;;
    --force-site) FORCE_SITE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "::error::$*" >&2; exit 1; }

echo "Deploying origin/main to ${SERVING_SSH_HOST#*@}"
git fetch origin main --quiet
echo "  local origin/main: $(git rev-parse --short origin/main)"

# ---------------------------------------------------------------- pipeline ---
if [ "$DO_PIPELINE" = 1 ]; then
  echo
  echo "[pipeline] $PIPELINE_DIR/repo"
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
fi

# -------------------------------------------------------------------- site ---
# Only rebuilt when something under site/ actually changed. The image takes minutes to build
# on two shared vCPUs, and a needless rebuild is also a needless dependency resolution —
# which is precisely how Streamlit 1.62 arrived unannounced and broke the nav.
echo
echo "[site] $SITE_DIR"
local_hash=$(cd site && find . -type f ! -name '*.pyc' ! -path './__pycache__/*' \
             -exec shasum {} + | sort -k2 | shasum | cut -d' ' -f1)
remote_hash=$("${SSH[@]}" "cd $SITE_DIR 2>/dev/null && find . -type f ! -name '*.pyc' \
              ! -path './__pycache__/*' ! -name '*.bak-*' -exec sha1sum {} + | sort -k2 | \
              sha1sum | cut -d' ' -f1" || echo none)

if [ "$local_hash" = "$remote_hash" ] && [ "$FORCE_SITE" = 0 ]; then
  echo "  unchanged, not rebuilding"
else
  echo "  syncing site/ ..."
  # COPYFILE_DISABLE stops macOS tar emitting AppleDouble `._*` companions. Those matched
  # the raw loader's *.json glob during the migration and would land inside the image here.
  COPYFILE_DISABLE=1 tar czf - -C site . \
    | "${SSH[@]}" "tar xzf - -C $SITE_DIR && find $SITE_DIR -name '._*' -delete"
  echo "  rebuilding image..."
  "${SSH[@]}" "cd /opt/cfdb && docker compose build site >/dev/null 2>&1 && \
               docker compose up -d site >/dev/null 2>&1"
  sleep 12
fi

# THE SITE IS NOT DEPLOYED UNTIL IT RENDERS. "The data is correct" and "the site works" are
# different claims (CLAUDE.md, 2026-08-31); this checks the second one.
echo "  verifying..."
scp -q -o BatchMode=yes ci/site_smoke.py "$SERVING_SSH_HOST:/tmp/site_smoke.py"
smoke=$("${SSH[@]}" "cd /opt/cfdb && docker compose cp /tmp/site_smoke.py site:/app/site_smoke.py \
          >/dev/null 2>&1 && docker compose exec -T site python /app/site_smoke.py 2>&1 \
          | grep -E '^OK|^FAIL'" || true)
echo "    ${smoke:-no output from the smoke test}"
case "$smoke" in OK*) ;; *) fail "site smoke test did not pass" ;; esac

health=$("${SSH[@]}" "cd /opt/cfdb && docker compose exec -T site python -c \
  \"import urllib.request;print(urllib.request.urlopen('http://localhost:8501/_stcore/health',timeout=15).read().decode())\" \
  2>/dev/null" || true)
echo "    health: ${health:-unreachable}"
case "$health" in ok*) ;; *) fail "site did not report healthy" ;; esac

echo
echo "Deployed."
