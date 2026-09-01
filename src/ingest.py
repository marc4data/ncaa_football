"""Ingestion utility: fetch CFBD endpoints and write raw JSON immutably.

Usage:
  CFBD_API_KEY=... python -m src.ingest fetch teams
  CFBD_API_KEY=... python -m src.ingest fetch games --year 2024

Files are written under `data/raw/<endpoint>/` with an ISO timestamp filename.
"""
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv

from .raw_manifest import RawManifest

load_dotenv()

CFBD_API_KEY = os.getenv("CFBD_API_KEY")
BASE_URL = "https://api.collegefootballdata.com"

manifest = RawManifest()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_raw(endpoint: str, content: dict):
    # Explicit format, not isoformat(): the UTC offset would introduce a "+00:00"
    # that the colon-stripping mangles into "+00-00". Filenames are manifest keys.
    #
    # Millisecond precision is load-bearing, not decoration. At second resolution two
    # fast responses (small endpoints answer in well under a second) produce the same
    # filename: the second write silently overwrites the first, and the manifest refuses
    # the duplicate filename — leaving a file labelled with the wrong request's params.
    # That happened to 6 files during the first 2024-25 backfill.
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
    dir_path = Path("data") / "raw" / endpoint
    ensure_dir(dir_path)

    # Belt and braces: never overwrite an existing raw file, whatever the clock says.
    filename = f"{ts}Z.json"
    file_path = dir_path / filename
    collision = 0
    while file_path.exists():
        collision += 1
        filename = f"{ts}Z-{collision}.json"
        file_path = dir_path / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    print(f"Wrote raw file: {file_path}")
    return filename


# (connect, read) rather than one number, and the read half is generous on purpose.
#
# A flat 30s killed the passing backfill on its FIRST request. Two things make 30s too tight
# here: several endpoints are computed rather than looked up — /game/box/advanced measured
# 1.4s, 4.2s and 20.2s across three consecutive calls — and /passing/plays returns 5.9 MB for
# a single week, which is a slow read on a two-vCPU box already running another backfill.
#
# The connect half stays short because a connection that will not establish in ten seconds is
# not going to; it is the body that legitimately takes minutes.
REQUEST_TIMEOUT = (10, 180)


def fetch(endpoint: str, params: dict | None = None):
    if not CFBD_API_KEY:
        print("CFBD_API_KEY not set. Export it or create a .env file.")
        sys.exit(1)
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {CFBD_API_KEY}"}
    resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    try:
        data = resp.json()
    except Exception:
        data = {"status_code": resp.status_code, "text": resp.text}
    endpoint_key = endpoint.replace('/', '_')
    filename = write_raw(endpoint_key, {"status_code": resp.status_code, "params": params, "data": data})
    try:
        recorded = manifest.add_entry(endpoint_key, filename, params, resp.status_code)
    except Exception:
        # I/O trouble writing the manifest shouldn't discard a response we already hold.
        print("Warning: failed to update raw manifest")
        return resp

    if not recorded:
        # The manifest refused the filename as a duplicate. The raw file is on disk but
        # its provenance is not recorded — exactly the unlabelled-data case the raw layer
        # exists to prevent, so fail loudly rather than continue.
        raise RuntimeError(
            f"Manifest refused duplicate filename {endpoint_key}/{filename}. "
            "The raw file's provenance is unrecorded; do not trust this fetch."
        )
    return resp


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "fetch":
        print("Usage: python -m src.ingest fetch <endpoint> [--key value ...]")
        return
    endpoint = sys.argv[2]
    params = {}
    # simple arg parsing for --key value
    i = 3
    while i < len(sys.argv):
        if sys.argv[i].startswith("--") and i + 1 < len(sys.argv):
            params[sys.argv[i][2:]] = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    fetch(endpoint, params)


if __name__ == "__main__":
    main()
