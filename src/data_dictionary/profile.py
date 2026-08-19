"""Measure what actually landed in `data/raw`.

CFBD states the grain of an endpoint nowhere — not in the spec, not in the docs. So grain has
to be derived, and the only honest way to derive it is to test key uniqueness against the
files on disk.

Two traps this module exists to avoid:

1.  `manifest.json` sits in every raw directory and is not data. Reading it as data yields a
    record set keyed by `filename`, which looks like a perfectly good grain and is nonsense.
2.  The same request is re-issued over time — nightly refreshes, snapshot endpoints. Testing
    uniqueness across files therefore fails on repeat-fetch duplicates rather than on any
    property of the data. Grain is tested WITHIN the largest single file; agreement across
    files is reported separately, as a flag rather than a conclusion.
"""
import collections
import itertools
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

MANIFEST = "manifest.json"
MAX_RECORDS = 6000
MAX_FILES = 3
MAX_FILE_BYTES = 60_000_000
EMPTY_FILE_BYTES = 200
MAX_KEY_COLUMNS = 3
MAX_CANDIDATES = 9

# Only columns whose names suggest identity are worth testing as keys; testing every column
# makes the combinatorics explode and produces coincidental keys on small samples.
KEY_HINTS = (
    "id", "season", "year", "week", "team", "school", "conference", "seasontype",
    "athlete", "player", "coach", "name", "category", "stattype", "provider",
    "poll", "classification", "startdate", "date",
)


def payload_files(directory: Path) -> List[Path]:
    return sorted(p for p in directory.glob("*.json") if p.name != MANIFEST)


def records_of(doc):
    """Raw payloads come in more than one shape; a loader must handle all of them."""
    if isinstance(doc, list):
        return doc, "bare_array"
    if isinstance(doc, dict) and "data" in doc:
        data = doc["data"]
        return (data if isinstance(data, list) else [data]), "wrapped"
    return [doc], "bare_object"


def _read(path: Path):
    try:
        with path.open() as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def candidate_keys(records: List[dict]) -> List[str]:
    present, nulls, distinct = collections.Counter(), collections.Counter(), collections.defaultdict(set)
    for record in records:
        for key, value in record.items():
            present[key] += 1
            if isinstance(value, (dict, list)):
                continue
            if value is None:
                nulls[key] += 1
            elif len(distinct[key]) < 500:
                distinct[key].add(str(value)[:60])
    total = len(records)
    nested = {k for r in records for k, v in r.items() if isinstance(v, (dict, list))}
    usable = [
        k for k in present
        if k not in nested and nulls[k] == 0 and present[k] == total
        and any(hint in k.lower() for hint in KEY_HINTS)
    ]
    return sorted(usable, key=lambda k: -len(distinct[k]))[:MAX_CANDIDATES]


def unique_combos(records: List[dict], candidates: List[str]) -> List[List[str]]:
    """Smallest column combinations that are unique across `records`."""
    found: List[List[str]] = []
    for size in range(1, MAX_KEY_COLUMNS + 1):
        for combo in itertools.combinations(candidates, size):
            if any(set(known) < set(combo) for known in found):
                continue
            seen, ok = set(), True
            for record in records:
                identity = tuple(str(record.get(column)) for column in combo)
                if identity in seen:
                    ok = False
                    break
                seen.add(identity)
            if ok:
                found.append(list(combo))
        if found:
            break
    return found


def profile_endpoint(directory: Path) -> dict:
    files = payload_files(directory)
    empty = sum(1 for f in files if f.stat().st_size < EMPTY_FILE_BYTES)
    sampled = sorted((f for f in files if f.stat().st_size < MAX_FILE_BYTES),
                     key=lambda f: f.stat().st_size, reverse=True)[:MAX_FILES]

    manifest = _read(directory / MANIFEST) or []
    param_keys = sorted({k for e in manifest for k in (e.get("params") or {})}) if manifest else []
    failures = collections.Counter(
        e.get("status_code") for e in manifest if e.get("status_code") != 200)

    records, shapes, grain_records = [], set(), []
    for path in sampled:
        doc = _read(path)
        if doc is None:
            continue
        rows, shape = records_of(doc)
        shapes.add(shape)
        rows = [r for r in rows if isinstance(r, dict)]
        if len(rows) > len(grain_records):
            grain_records = rows[:MAX_RECORDS]
        records.extend(rows)
        if len(records) >= MAX_RECORDS:
            break
    records = records[:MAX_RECORDS]

    result = dict(
        key=directory.name, files=len(files), empty_files=empty, files_sampled=len(sampled),
        manifest_calls=len(manifest), failed_calls=dict(failures), param_keys=param_keys,
        shapes=sorted(shapes), records_sampled=len(records),
        grain_rows=len(grain_records), keys={}, nested=[], unique=[], cross_file={},
    )
    if not records:
        return result

    present, nulls, distinct = collections.Counter(), collections.Counter(), collections.defaultdict(set)
    nested = set()
    for record in records:
        for key, value in record.items():
            present[key] += 1
            if isinstance(value, (dict, list)):
                nested.add(key)
            elif value is None:
                nulls[key] += 1
            elif len(distinct[key]) < 200:
                distinct[key].add(str(value)[:60])

    total = len(records)
    for key in present:
        count = len(distinct[key])
        result["keys"][key] = dict(
            present_pct=round(100.0 * present[key] / total, 1),
            null_pct=round(100.0 * nulls[key] / total, 1),
            distinct=count if count < 200 else "200+",
            samples=sorted(distinct[key])[:8 if count <= 12 else 3],
        )
    result["nested"] = sorted(nested)
    result["unique"] = unique_combos(grain_records, candidate_keys(grain_records))[:6]

    # Does the within-file key survive across files, once byte-identical repeat-fetch rows are
    # dropped? Disagreement means a wider true grain OR rows that mutate between fetches.
    deduped, seen = [], set()
    for record in records:
        fingerprint = json.dumps(record, sort_keys=True, default=str)
        if fingerprint not in seen:
            seen.add(fingerprint)
            deduped.append(record)
    for combo in result["unique"][:3]:
        identities = [tuple(str(r.get(c)) for c in combo) for r in deduped]
        result["cross_file"]["+".join(combo)] = dict(
            deduped_rows=len(deduped), duplicate_keys=len(identities) - len(set(identities)))
    return result


def profile_all(raw_dir: Path, keys: Optional[List[str]] = None) -> Dict[str, dict]:
    out = {}
    for directory in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        if keys is not None and directory.name not in keys:
            continue
        out[directory.name] = profile_endpoint(directory)
    return out


def landed_keys(raw_dir: Path) -> List[str]:
    """Raw directories that hold at least one payload file."""
    return sorted(d.name for d in raw_dir.iterdir()
                  if d.is_dir() and payload_files(d))


__all__ = ["profile_all", "profile_endpoint", "landed_keys", "records_of",
           "payload_files", "unique_combos", "candidate_keys"]


if __name__ == "__main__":  # pragma: no cover
    import argparse
    parser = argparse.ArgumentParser(description="Profile the landed raw corpus.")
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--out", default="data/observed_profile.json")
    args = parser.parse_args()
    profile = profile_all(Path(args.raw))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(profile, fh, indent=2)
    print("profiled {} endpoints -> {}".format(len(profile), args.out))
