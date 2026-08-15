import os
import json
from pathlib import Path
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "cfdb")
PG_PASSWORD = os.getenv("PG_PASSWORD", "cfdb")
PG_DB = os.getenv("PG_DB", "cfdb")


def get_conn():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB)


def load_endpoint(endpoint: str):
    base = Path("data") / "raw" / endpoint
    if not base.exists():
        print("No raw data for endpoint:", endpoint)
        return
    files = sorted([p for p in base.iterdir() if p.suffix == ".json" and p.name != "manifest.json"])
    if not files:
        print("No json files to load for endpoint:", endpoint)
        return

    # When the response was *observed*, from the manifest. Distinct from load time: a
    # snapshot endpoint like /lines is fetched repeatedly with identical params, and the
    # movement between fetches is only interpretable against the fetch timestamp.
    fetched_at = {}
    manifest_path = base / "manifest.json"
    if manifest_path.exists():
        try:
            for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
                fetched_at[entry["filename"]] = entry.get("added_at")
        except json.JSONDecodeError:
            print(f"Warning: unreadable manifest for {endpoint}; fetched_at will be null")

    table = f"raw_{endpoint}"
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    filename text PRIMARY KEY,
                    content jsonb,
                    status_code int,
                    params jsonb,
                    fetched_at timestamptz,
                    added_at timestamptz
                );
                """
            )
            # Tables created before fetched_at existed.
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS fetched_at timestamptz;")
            for p in files:
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    payload = {"_raw_text": p.read_text()}
                status_code = payload.get("status_code") if isinstance(payload, dict) else None
                params = payload.get("params") if isinstance(payload, dict) else None
                cur.execute(
                    f"""
                    INSERT INTO {table}
                        (filename, content, status_code, params, fetched_at, added_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (filename) DO UPDATE SET
                        content = EXCLUDED.content,
                        status_code = EXCLUDED.status_code,
                        params = EXCLUDED.params,
                        fetched_at = EXCLUDED.fetched_at,
                        added_at = EXCLUDED.added_at;
                    """,
                    (p.name, json.dumps(payload), status_code,
                     json.dumps(params) if params is not None else None,
                     fetched_at.get(p.name)),
                )
    conn.close()
    print(f"Loaded {len(files)} files into {table}")


def load_all():
    """Load every endpoint directory present under data/raw.

    With 63 endpoints in the sweep, naming each one is no longer practical. Directories
    are discovered from disk rather than the registry so that anything landed by hand
    (a one-off `src.ingest` call) is loaded too.
    """
    base = Path("data") / "raw"
    if not base.exists():
        print("No raw data to load.")
        return
    endpoints = sorted(p.name for p in base.iterdir() if p.is_dir())
    for endpoint in endpoints:
        load_endpoint(endpoint)
    print(f"\nLoaded {len(endpoints)} endpoint(s).")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.load_raw_to_postgres <endpoint>|--all")
    elif sys.argv[1] == "--all":
        load_all()
    else:
        load_endpoint(sys.argv[1])
