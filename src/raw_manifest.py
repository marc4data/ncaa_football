from pathlib import Path
import json
from datetime import datetime
from typing import Any, Dict, List


class RawManifest:
    """Simple per-endpoint manifest for immutable raw files.

    Stores a `manifest.json` under `data/raw/<endpoint>/manifest.json` with
    entries describing each fetched file: filename, params, status_code, added_at.
    """

    def __init__(self, base_dir: Path | str = Path("data") / "raw"):
        self.base_dir = Path(base_dir)

    def _ensure_dir(self, endpoint: str) -> Path:
        p = self.base_dir / endpoint
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _manifest_path(self, endpoint: str) -> Path:
        return self.base_dir / endpoint / "manifest.json"

    def _load(self, endpoint: str) -> List[Dict[str, Any]]:
        mp = self._manifest_path(endpoint)
        if not mp.exists():
            return []
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, endpoint: str, entries: List[Dict[str, Any]]):
        mp = self._manifest_path(endpoint)
        mp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_entry(self, endpoint: str, filename: str, params: Dict[str, Any] | None, status_code: int) -> bool:
        """Add a manifest entry. Returns False if an entry with the same filename already exists."""
        self._ensure_dir(endpoint)
        entries = self._load(endpoint)
        for e in entries:
            if e.get("filename") == filename:
                return False
        entry = {
            "filename": filename,
            "params": params or {},
            "status_code": status_code,
            "added_at": datetime.utcnow().isoformat()
        }
        entries.append(entry)
        self._save(endpoint, entries)
        return True

    def exists(self, endpoint: str, params: Dict[str, Any] | None) -> bool:
        entries = self._load(endpoint)
        for e in entries:
            if e.get("params") == (params or {}):
                return True
        return False

    def list_entries(self, endpoint: str) -> List[Dict[str, Any]]:
        return self._load(endpoint)


if __name__ == "__main__":
    m = RawManifest()
    print(m.list_entries("test"))
