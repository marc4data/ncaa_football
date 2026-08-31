#!/usr/bin/env python3
"""Refresh the vendored CFBD OpenAPI spec, or check the vendored copy against upstream.

WHY THE SPEC IS VENDORED AT ALL. The 24 Aug decision was to reference it by URL and ignore
the file, on the grounds that a vendored copy goes stale. The staleness was real — the URL
served 5.24.0 then and serves 5.25.0 now — but a URL cannot anchor anything.

`docs/cfbd_coverage.md` is a committed claim about which endpoints exist, which we register,
which have landed raw, and which fields we unnest. Its denominator is the spec. Anchored to a
URL, that claim quietly means something different every time upstream ships, and no diff ever
shows it. Anchored to a committed file, upstream drift is a visible change to a tracked
artifact — which is how the five `passing/*` paths surfaced at all.

So staleness is not avoided here, it is made loud:

    python scripts/refresh_cfbd_spec.py            # fetch and write
    python scripts/refresh_cfbd_spec.py --check    # exit 1 if vendored != upstream

`--check` runs in CI. It fetches, so it needs the network and no API key: the spec is served
unauthenticated because it describes a public API.

THE FILE IS NORMALIZED, NOT COPIED BYTE FOR BYTE. Upstream's key order is generator output
and is not stable between releases; sorting keys and fixing the indent means a real change to
one endpoint shows up as a few lines instead of a reshuffle of 5,000. The cost is that the
vendored file is not literally the bytes upstream serves — acceptable because this script is
the only way it is written, and `--check` compares normalized against normalized.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

SPEC_URL = "https://api.collegefootballdata.com/api-docs.json"
VENDORED = Path(__file__).resolve().parents[1] / "config" / "api-docs.json"
TIMEOUT_SECONDS = 60


def normalize(spec: dict) -> str:
    """Deterministic on-disk form: sorted keys, two-space indent, trailing newline."""
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def fetch(url: str = SPEC_URL) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def summarize(spec: dict) -> str:
    return (f"v{spec['info']['version']} — {len(spec['paths'])} paths, "
            f"{len(spec.get('components', {}).get('schemas', {}))} schemas")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare only; exit 1 if the vendored copy is out of date")
    args = parser.parse_args(argv)

    upstream = fetch()
    rendered = normalize(upstream)
    current = VENDORED.read_text() if VENDORED.exists() else ""

    if args.check:
        if current == rendered:
            print(f"config/api-docs.json is current: {summarize(upstream)}")
            return 0
        # Naming what moved, because "the spec changed" sends the reader to a 5,000-line
        # diff to find out whether it matters.
        print(f"::error::config/api-docs.json is out of date. "
              f"Vendored: {summarize(json.loads(current)) if current else 'missing'}. "
              f"Upstream: {summarize(upstream)}.", file=sys.stderr)
        if current:
            old_paths = set(json.loads(current)["paths"])
            new_paths = set(upstream["paths"])
            for path in sorted(new_paths - old_paths):
                print(f"  + {path}", file=sys.stderr)
            for path in sorted(old_paths - new_paths):
                print(f"  - {path}", file=sys.stderr)
        print("Run: python scripts/refresh_cfbd_spec.py", file=sys.stderr)
        return 1

    VENDORED.write_text(rendered)
    verb = "unchanged" if current == rendered else "updated"
    print(f"config/api-docs.json {verb}: {summarize(upstream)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
