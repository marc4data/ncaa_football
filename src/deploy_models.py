"""Rebuild and publish only the models a deploy actually changed.

WHY THIS EXISTS. `scripts/deploy_main.sh` rebuilt every production model whenever anything
under `dbt/models/serving/` moved: 95 models, 328 seconds, measured on 2026-09-04. The change
that triggered it touched one model. Rebuilding that one and its children takes 18.

The old trigger was a directory diff, and its own comment recorded the blind spot: a change to
an UPSTREAM model — fct_game, dim_team, a staging view — alters serving output without
touching `dbt/models/serving/`, so it was MISSED and needed `--rebuild` by hand. R-127 was
exactly that shape.

`state:modified+` fixes both halves at once. It compares the code against the manifest from
the last successful deploy, so it sees a changed macro or a changed upstream model, and the
`+` carries the rebuild downstream to every serving table that reads it. Faster AND stricter
is unusual; it is available here because dbt already writes the artefact that makes it
possible and nothing was reading it.

THE MANIFEST IS ONLY SNAPSHOTTED AFTER BOTH STEPS SUCCEED. If the run works and the publish
fails, the next deploy must still see those models as un-deployed — otherwise one bad publish
makes the change invisible to every deploy that follows, which is a silent stale-data bug of
exactly the kind this project keeps finding.

FALLING BACK IS ALWAYS TO MORE WORK, NEVER LESS. No previous manifest, an unreadable one, a
dbt version that rejects it — every one of those rebuilds everything. A deploy that does too
much is slow; a deploy that does too little ships a half-built warehouse.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_DIR = Path(os.environ.get("CFDB_DBT_PROJECT_DIR", "/opt/airflow/project/dbt"))

# WHERE DBT ACTUALLY WRITES, WHICH IS NOT `<project>/target` HERE.
#
# The container sets DBT_TARGET_PATH=/opt/airflow/dbt-state/target so the artefacts land on a
# writable volume rather than inside a root-owned checkout. `<project>/target` DOES exist on
# the droplet and holds a manifest from 31 August, owned by uid 501 — a macOS uid, left by a
# laptop run before the migration. Reading it would have published against five-day-old
# metadata and looked completely normal doing it.
#
# Read from the environment rather than hardcoded, because the env var is the thing that is
# actually true and a second copy of it here is a second thing to keep in step.
TARGET_DIR = Path(os.environ.get("DBT_TARGET_PATH", str(PROJECT_DIR / "target")))

# The manifest from the last deploy that fully succeeded. Deliberately NOT `target/`, which
# every dbt run overwrites — comparing a run against itself finds nothing modified, which
# would silently turn every deploy into a no-op.
DEPLOYED_STATE = Path(
    os.environ.get("CFDB_DEPLOYED_STATE", "/opt/airflow/dbt-state/deployed"))

FULL_SELECTOR = "+tag:production"
# Comma is INTERSECTION in dbt's selector syntax, space is union. This is "everything modified
# or downstream of something modified, that is also part of the production surface".
CHANGED_SELECTOR = "state:modified+,tag:production"

SERVING_SCHEMA = "serving"


def previous_manifest() -> Optional[Path]:
    """The last successfully-deployed manifest, or None if there is not one to compare to."""
    candidate = DEPLOYED_STATE / "manifest.json"
    if not candidate.is_file():
        return None
    try:
        json.loads(candidate.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # A truncated manifest is worse than none: dbt would either error or, worse, compare
        # against a partial graph and under-select. Treat it as absent.
        return None
    return candidate


def choose_selector(full: bool, previous: Optional[Path]) -> Tuple[str, str]:
    """(selector, why). The `why` is printed, because a deploy that quietly did less than you
    expected is indistinguishable from one that did nothing."""
    if full:
        return FULL_SELECTOR, "--full requested"
    if previous is None:
        return FULL_SELECTOR, "no previous manifest to compare against"
    return CHANGED_SELECTOR, f"comparing against {previous}"


def run_dbt(selector: str, state: Optional[Path]) -> subprocess.CompletedProcess:
    command = ["dbt", "run", "--project-dir", str(PROJECT_DIR), "--select", selector]
    if state is not None:
        command += ["--state", str(state.parent)]
    return subprocess.run(command, capture_output=True, text=True)


def models_built(run_results: Path, manifest: Path) -> List[str]:
    """Names of models this run actually created, in the serving schema.

    Read from dbt's own run_results rather than re-derived from the selector: the selector
    says what was ASKED for and this says what happened, and the publish must ship the
    second. A model that errored must not be published as though it had been rebuilt.
    """
    results = json.loads(run_results.read_text(encoding="utf-8"))
    nodes = json.loads(manifest.read_text(encoding="utf-8")).get("nodes", {})
    built = []
    for entry in results.get("results", []):
        if entry.get("status") != "success":
            continue
        node = nodes.get(entry.get("unique_id"), {})
        if node.get("resource_type") != "model":
            continue
        if node.get("schema") != SERVING_SCHEMA:
            continue
        built.append(node.get("alias") or node.get("name"))
    return sorted(set(n for n in built if n))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true",
                        help="rebuild every production model, whatever changed")
    args = parser.parse_args(argv)

    previous = previous_manifest()
    selector, why = choose_selector(args.full, previous)
    print(f"  selector: {selector}  ({why})")

    started = time.time()
    completed = run_dbt(selector, previous)
    tail = "\n".join((completed.stdout or "").strip().splitlines()[-3:])
    if completed.returncode != 0:
        print(tail or (completed.stderr or "").strip()[-500:])
        # A state comparison that cannot run is a reason to do MORE, not to give up: a dbt
        # upgrade changes the manifest schema version and this is where that surfaces.
        if selector != FULL_SELECTOR:
            print("  state comparison failed — falling back to a full rebuild")
            completed = run_dbt(FULL_SELECTOR, None)
            tail = "\n".join((completed.stdout or "").strip().splitlines()[-3:])
            if completed.returncode != 0:
                print(tail)
                return 1
        else:
            return 1
    print(f"  {tail.splitlines()[-1] if tail else 'dbt finished'}")

    run_results = TARGET_DIR / "run_results.json"
    manifest = TARGET_DIR / "manifest.json"
    if not run_results.is_file() or not manifest.is_file():
        print("  ::error:: dbt left no artefacts to read; refusing to guess what to publish")
        return 1

    # THE ARTEFACTS MUST BE FROM THE RUN THAT JUST HAPPENED.
    #
    # Pointing at the wrong target directory is not hypothetical — the first version of this
    # module did, and `<project>/target` on the droplet holds a manifest from five days
    # earlier. That would publish a plausible-looking set of tables chosen from stale
    # metadata, with nothing anywhere to say so. Cheap to rule out, impossible to spot later.
    for artefact in (run_results, manifest):
        if artefact.stat().st_mtime < started:
            print(f"  ::error:: {artefact} was not written by this run — "
                  f"DBT_TARGET_PATH is probably not what this module thinks it is")
            return 1

    tables = models_built(run_results, manifest)
    if not tables:
        print("  nothing in the serving layer changed; no publish needed")
    else:
        # Intersected with the contracted list so a new or renamed model cannot be shipped to
        # the site before anybody has decided it should be.
        from src.publish_marts import DEFAULT_SERVING, publish_schema
        shipping = [t for t in tables if t in DEFAULT_SERVING]
        skipped = [t for t in tables if t not in DEFAULT_SERVING]
        if skipped:
            print(f"  not published (not in the contracted serving list): {', '.join(skipped)}")
        if shipping:
            print(f"  publishing {len(shipping)}: {', '.join(shipping)}")
            publish_schema(shipping, SERVING_SCHEMA)

    # ONLY NOW. Snapshotting earlier would mark this change deployed even if the publish
    # raised, and every later deploy would then see nothing to do.
    DEPLOYED_STATE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, DEPLOYED_STATE / "manifest.json")
    print(f"  recorded this build as deployed ({DEPLOYED_STATE / 'manifest.json'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
