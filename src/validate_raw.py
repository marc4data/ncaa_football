"""Audit the raw layer: does every manifest entry describe the file it points at?

Raw files are self-describing — each stores the `params` of the request that produced it —
so the manifest can be checked against the data rather than trusted. Runs in seconds and
should be run after any backfill.

  python -m src.validate_raw            # audit everything under data/raw
  python -m src.validate_raw --repair   # additionally delete mismatched files + entries

Checks:
  1. MISMATCH — manifest params != the params recorded inside the file (the file was
     overwritten by a different request; the dangerous one, since it corrupts silently).
  2. MISSING  — manifest lists a file that isn't on disk.
  3. ORPHAN   — a raw file on disk that no manifest entry claims.

Exits non-zero if anything is wrong, so it can gate a pipeline step.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

RAW_ROOT = Path("data") / "raw"


def audit(root: Path = RAW_ROOT) -> Tuple[List[str], List[str], List[str]]:
    mismatched: List[str] = []
    missing: List[str] = []
    orphans: List[str] = []

    if not root.exists():
        return mismatched, missing, orphans

    for endpoint_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest_path = endpoint_dir / "manifest.json"
        entries: List[Dict[str, Any]] = []
        if manifest_path.exists():
            try:
                entries = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                mismatched.append(f"{endpoint_dir.name}/manifest.json is not valid JSON")
                continue

        on_disk = {p.name for p in endpoint_dir.iterdir()
                   if p.suffix == ".json" and p.name != "manifest.json"}
        listed = set()

        for entry in entries:
            filename = entry.get("filename")
            listed.add(filename)
            path = endpoint_dir / filename
            if not path.exists():
                missing.append(f"{endpoint_dir.name}/{filename}")
                continue
            try:
                on_file = json.loads(path.read_text(encoding="utf-8")).get("params")
            except json.JSONDecodeError:
                mismatched.append(f"{endpoint_dir.name}/{filename} is not valid JSON")
                continue
            if on_file != entry.get("params"):
                mismatched.append(
                    f"{endpoint_dir.name}/{filename}: manifest says {entry.get('params')}, "
                    f"file contains {on_file}"
                )

        for filename in sorted(on_disk - listed):
            orphans.append(f"{endpoint_dir.name}/{filename}")

    return mismatched, missing, orphans


def repair(mismatched: List[str], root: Path = RAW_ROOT) -> int:
    """Delete mismatched files and drop their manifest entries.

    Deliberately does not re-fetch — rerun `python -m src.backfill` for that. Removing the
    entry is what makes the backfill's skip-if-present logic pick the request back up.
    """
    removed = 0
    by_dir: Dict[str, List[str]] = {}
    for item in mismatched:
        ref = item.split(":")[0]
        endpoint, _, filename = ref.partition("/")
        by_dir.setdefault(endpoint, []).append(filename)

    for endpoint, filenames in by_dir.items():
        endpoint_dir = root / endpoint
        manifest_path = endpoint_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        kept = [e for e in entries if e.get("filename") not in filenames]
        manifest_path.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")
        for filename in filenames:
            path = endpoint_dir / filename
            if path.exists():
                path.unlink()
                removed += 1
            print(f"  removed {endpoint}/{filename}")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the raw layer against its manifests.")
    parser.add_argument("--repair", action="store_true",
                        help="delete mismatched files and their manifest entries")
    args = parser.parse_args()

    mismatched, missing, orphans = audit()

    print(f"MISMATCHED: {len(mismatched)}")
    for item in mismatched:
        print(f"  {item}")
    print(f"MISSING: {len(missing)}")
    for item in missing:
        print(f"  {item}")
    print(f"ORPHANS: {len(orphans)}")
    for item in orphans:
        print(f"  {item}")

    if args.repair and mismatched:
        print("\nRepairing mismatched entries:")
        removed = repair(mismatched)
        print(f"Removed {removed} file(s). Re-run `python -m src.backfill` to refetch them.")
        return 0

    return 1 if (mismatched or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
