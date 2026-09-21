from pathlib import Path
import json
from datetime import datetime, timezone
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
            "added_at": datetime.now(timezone.utc).isoformat()
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

    def succeeded_since(self, endpoint: str, params: Dict[str, Any] | None,
                        cutoff: "datetime") -> bool:
        """Did THIS exact request already come back 200 at or after `cutoff`?

        🚨 A185 (cfdb-main-R-1916). `exists()` ABOVE CANNOT ANSWER THIS AND MUST NOT BE USED
        FOR IT: it matches on params alone and ignores `status_code`, so a request that came
        back 429 counts as present. A retry keyed on `exists()` would skip precisely the
        requests that failed — the exact inverse of what a retry is for.

        ⚠️ AND THE CUTOFF IS THE OTHER HALF. Without it this would mean "ever fetched", and a
        weekly refresh would stop re-fetching the REVISIONIST bucket, which exists because
        that data revises. The window scopes the answer to the run in progress: retries are
        minutes apart and runs are a week apart, so anything inside a few hours belongs to
        this attempt's predecessors.
        """
        for e in self._load(endpoint):
            if e.get("params") != (params or {}):
                continue
            if e.get("status_code") != 200:
                continue
            stamp = e.get("added_at")
            if not stamp:
                continue
            try:
                added = datetime.fromisoformat(stamp)
            except ValueError:
                continue
            if added.tzinfo is None:
                added = added.replace(tzinfo=timezone.utc)
            if added >= cutoff:
                return True
        return False

    def list_entries(self, endpoint: str) -> List[Dict[str, Any]]:
        return self._load(endpoint)


if __name__ == "__main__":
    m = RawManifest()
    print(m.list_entries("test"))
