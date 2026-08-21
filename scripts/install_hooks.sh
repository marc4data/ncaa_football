#!/usr/bin/env bash
#
# Install the repository's git hooks.
#
# Hooks live in scripts/ and are COPIED into .git/hooks, because .git/hooks is not version
# controlled — a hook that exists only on one machine protects only that machine, and the
# whole point of this one is that it protects a repository which is now public.
#
# Run once after cloning:  bash scripts/install_hooks.sh
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
install -m 0755 "$root/scripts/pre-commit" "$root/.git/hooks/pre-commit"
echo "Installed pre-commit hook -> .git/hooks/pre-commit"
echo "It refuses any staged path under cfdb_model_pack/ or model_outputs/, and any"
echo "training_data.csv, *.joblib, *.pkl or *.pth by name."
