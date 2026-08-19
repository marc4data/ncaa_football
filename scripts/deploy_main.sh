#!/usr/bin/env bash
# Refresh the Airflow deploy tree to the current origin/main.
#
# Airflow bind-mounts ../cfdb_deploy, a worktree pinned to main, so merging a PR does NOT
# change what Airflow runs until this is run. That is the point: deployment becomes a
# deliberate act rather than a side effect of whatever branch happens to be checked out.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../cfdb_deploy" && pwd)"

echo "Deploy tree: $DEPLOY_DIR"
git -C "$DEPLOY_DIR" fetch origin main --quiet
before=$(git -C "$DEPLOY_DIR" rev-parse --short HEAD)
git -C "$DEPLOY_DIR" reset --hard origin/main --quiet
after=$(git -C "$DEPLOY_DIR" rev-parse --short HEAD)

if [ "$before" = "$after" ]; then
  echo "Already at $after — nothing to deploy."
else
  echo "Deployed $before -> $after"
  git -C "$DEPLOY_DIR" log --oneline "$before..$after" | sed 's/^/  /'
fi

# The DAG processor re-reads files from disk, so no restart is needed for a DAG change.
# Import errors are the thing worth surfacing immediately.
echo "Checking DAG imports..."
docker exec claude_code-airflow-scheduler-1 airflow dags list-import-errors 2>&1 \
  | grep -v "masking" | tail -3
