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

    table = f"raw_{endpoint}"
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} (filename text PRIMARY KEY, content jsonb, status_code int, params jsonb, added_at timestamptz);")
            for p in files:
                try:
                    payload = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    payload = {"_raw_text": p.read_text()}
                status_code = payload.get("status_code") if isinstance(payload, dict) else None
                params = payload.get("params") if isinstance(payload, dict) else None
                cur.execute(
                    f"INSERT INTO {table} (filename, content, status_code, params, added_at) VALUES (%s, %s, %s, %s, now()) ON CONFLICT (filename) DO UPDATE SET content=EXCLUDED.content, status_code=EXCLUDED.status_code, params=EXCLUDED.params, added_at=EXCLUDED.added_at;",
                    (p.name, json.dumps(payload), status_code, json.dumps(params) if params is not None else None),
                )
    conn.close()
    print(f"Loaded {len(files)} files into {table}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.load_raw_to_postgres <endpoint>")
    else:
        load_endpoint(sys.argv[1])
