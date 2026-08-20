"""Assert what `--select +tag:production` RESOLVES TO, not that it succeeded.

Three findings in four days shared one shape — green and useless:

  1. The deploy tree ran nine commits behind. Every build succeeded, and the next one would
     have reverted a day's work.
  2. `->> '0'` on a JSON array. Every extraction succeeded, returning null, masked by a
     fallback that was doing 100% of the work.
  3. `+tag:production` resolved to six models. Every refresh succeeded, rebuilding three
     legacy marts nothing reads and not one srv_ view.

None was visible from run status, because all three checked that a thing RAN and never that
it PRODUCED anything. This is that check for the third one.

The specific failure it prevents: the production selector is the boundary between "a model
exists" and "Airflow keeps it fresh". A serving view outside it is stale on the site from
the moment it ships, and there is no symptom — the page renders, the data is simply from
whenever somebody last ran dbt by hand.

Two assertions, and the second is the one that matters:

  Every serving model is in the selection.  Not a count threshold, which drifts and gets
                                            raised. Membership, per model, by name.
  Every ancestor is in the selection.       A serving view whose upstream mart is excluded
                                            is rebuilt from a stale input, which is worse
                                            than not rebuilding it at all: it looks fresh.

Runs against dbt's manifest, so it reads the compiled graph rather than re-implementing
selector semantics.
"""
import json
import sys
from pathlib import Path

MANIFEST = Path("dbt/target/manifest.json")
TAG = "production"


def main() -> int:
    if not MANIFEST.exists():
        print(f"::error::{MANIFEST} not found — run `dbt compile` or `dbt build` first")
        return 1

    manifest = json.loads(MANIFEST.read_text())
    nodes = {k: v for k, v in manifest.get("nodes", {}).items()
             if v.get("resource_type") == "model"}
    if not nodes:
        print("::error::manifest contains no models")
        return 1

    tagged = {k for k, v in nodes.items() if TAG in (v.get("tags") or [])}

    # `+tag:production` is tagged models plus all their ancestors, transitively.
    parents = {k: set(v.get("depends_on", {}).get("nodes", [])) for k, v in nodes.items()}
    selected, frontier = set(tagged), list(tagged)
    while frontier:
        current = frontier.pop()
        for parent in parents.get(current, ()):
            if parent in nodes and parent not in selected:
                selected.add(parent)
                frontier.append(parent)

    def layer(unique_id: str) -> str:
        parts = Path(nodes[unique_id].get("original_file_path", "")).parts
        for candidate in ("staging", "marts", "serving"):
            if candidate in parts:
                return candidate
        return "other"

    serving = {k for k in nodes if layer(k) == "serving"}
    failures = []

    missing_serving = sorted(nodes[k]["name"] for k in serving - selected)
    if missing_serving:
        failures.append(
            "serving model(s) OUTSIDE the production selection — Airflow will never "
            f"rebuild them: {', '.join(missing_serving)}")

    # An ancestor outside the selection is the subtler failure: the view rebuilds, from an
    # input that did not, and the result looks current.
    stale_inputs = []
    for node in sorted(selected):
        for parent in parents.get(node, ()):
            if parent in nodes and parent not in selected:
                stale_inputs.append(f"{nodes[node]['name']} <- {nodes[parent]['name']}")
    if stale_inputs:
        failures.append(
            "selected model(s) depend on models OUTSIDE the selection, so they would "
            f"rebuild from stale inputs: {', '.join(sorted(set(stale_inputs)))}")

    counts = {}
    for node in selected:
        counts[layer(node)] = counts.get(layer(node), 0) + 1
    print(f"`+tag:{TAG}` selects {len(selected)} of {len(nodes)} model(s): "
          + ", ".join(f"{n} {name}" for name, n in sorted(counts.items())))
    excluded = sorted(nodes[k]["name"] for k in set(nodes) - selected)
    print(f"Excluded ({len(excluded)}): {', '.join(excluded) if excluded else 'none'}")

    if failures:
        print()
        for failure in failures:
            print(f"::error::{failure}")
        return 1

    print("Every serving model and every ancestor is in the refresh Airflow runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
