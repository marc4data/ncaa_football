"""Assert the layer boundaries dbt can't enforce on its own.

Schema-per-layer separates the *output* of each layer. It does not stop a mart from
selecting straight out of raw and skipping staging entirely — the schemas would still look
tidy while the dependency graph had a hole in it.

This reads dbt's manifest, which records the real dependency edges after compilation, and
enforces two rules from the layering decision (2026-08-17):

  1. Only staging models may reference sources. A mart reading raw JSON directly means the
     cleaning, the status_code filter, and the dedup have all been bypassed.
  2. Marts may only depend on staging or other marts.

Run after any dbt compile/build:
    python ci/check_layering.py
"""
import json
import sys
from pathlib import Path

MANIFEST = Path("dbt/target/manifest.json")


def layer_of(node: dict) -> str:
    """Which layer a model belongs to, from its path rather than its name."""
    parts = Path(node.get("original_file_path", "")).parts
    if "staging" in parts:
        return "staging"
    if "marts" in parts:
        return "marts"
    return "other"


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} not found — run `dbt compile` or `dbt build` first")
        return 1

    manifest = json.loads(MANIFEST.read_text())
    nodes = manifest.get("nodes", {})
    violations = []

    for unique_id, node in nodes.items():
        if node.get("resource_type") != "model":
            continue
        layer = layer_of(node)
        depends_on = node.get("depends_on", {}).get("nodes", [])
        sources = [d for d in depends_on if d.startswith("source.")]
        models = [d for d in depends_on if d.startswith("model.")]

        if sources and layer != "staging":
            violations.append(
                f"{node['name']} ({layer}) references sources directly: "
                f"{', '.join(s.split('.')[-1] for s in sources)}"
            )

        if layer == "marts":
            for dep in models:
                dep_node = nodes.get(dep)
                if dep_node and layer_of(dep_node) == "other":
                    violations.append(
                        f"{node['name']} (marts) depends on {dep_node['name']}, "
                        f"which is in neither staging nor marts"
                    )

    staging = [n for n in nodes.values()
               if n.get("resource_type") == "model" and layer_of(n) == "staging"]
    marts = [n for n in nodes.values()
             if n.get("resource_type") == "model" and layer_of(n) == "marts"]
    print(f"Checked {len(staging)} staging and {len(marts)} mart model(s).")

    if violations:
        print(f"\nLAYER VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  - {v}")
        print("\nOnly staging may read sources; marts build on staging.")
        return 1

    print("Layer boundaries hold: sources are read only by staging.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
