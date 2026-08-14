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
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(":", "-")
    dir_path = Path("data") / "raw" / endpoint
    ensure_dir(dir_path)
    filename = f"{ts}.json"
    file_path = dir_path / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    print(f"Wrote raw file: {file_path}")
    return filename


def fetch(endpoint: str, params: dict | None = None):
    if not CFBD_API_KEY:
        print("CFBD_API_KEY not set. Export it or create a .env file.")
        sys.exit(1)
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {CFBD_API_KEY}"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    try:
        data = resp.json()
    except Exception:
        data = {"status_code": resp.status_code, "text": resp.text}
    endpoint_key = endpoint.replace('/', '_')
    filename = write_raw(endpoint_key, {"status_code": resp.status_code, "params": params, "data": data})
    try:
        manifest.add_entry(endpoint_key, filename, params, resp.status_code)
    except Exception:
        # manifest failures should not stop the fetch
        print("Warning: failed to update raw manifest")
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
