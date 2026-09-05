import os
import json
from pathlib import Path
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# NO `localhost` FALLBACK, AND THIS IS THE FILE THAT MATTERS MOST FOR IT (R-312).
#
# get_conn() below is imported by every loader, by publish_marts, by deploy_status and by
# export_sample — so this one default decided where the whole pipeline wrote. It said
# `localhost:5432`, which since 2026-09-05 is a database that does not exist (R-296), and
# before that was a stale local stack. export_sample.py already carries the post-mortem: a
# serving export ran against it and produced a workbook with the right sheet names, the
# right structure and plausible row counts, describing a database from days ago. The only
# visible symptom was a table count somebody happened to question.
#
# A default that cannot work is worse than none: it does not error, it answers. Airflow sets
# PG_HOST on the compose network and CI sets it in the workflow env, so removing the
# fallback changes nothing in either — it fails only the case that was already wrong, a
# loader run by hand from a working copy with no tunnel and no .env.
#
# THE REFUSAL IS IN pg_params(), NOT AT IMPORT. Half this module is pure functions
# (payload_row_count and friends) that the unit tests import without ever opening a
# connection, and a module that cannot be imported without a warehouse would make every one
# of those tests need one. Fail where the database is actually wanted.
PG_USER = os.getenv("PG_USER", "cfdb")
PG_PASSWORD = os.getenv("PG_PASSWORD", "cfdb")
PG_DB = os.getenv("PG_DB", "cfdb")

_NO_TARGET = (
    "PG_HOST/PG_PORT are not set, and there is no default — deliberately. dbt and the "
    "loaders build in the droplet's WAREHOUSE; there is no local Postgres (dropped "
    "2026-09-05, R-296). Open scripts/warehouse_tunnel.sh, set CFDB_WAREHOUSE_HOST and "
    "CFDB_WAREHOUSE_PORT in .env (see .env.example), then run "
    "python scripts/preflight_env.py."
)


def pg_params() -> dict:
    """Connection parameters for the warehouse, or a refusal naming what to do about it.

    Read at call time rather than import time so that a working copy which fixes its .env
    does not have to restart a long-lived process to pick it up.
    """
    host = os.getenv("PG_HOST") or os.getenv("CFDB_WAREHOUSE_HOST") or ""
    port = os.getenv("PG_PORT") or os.getenv("CFDB_WAREHOUSE_PORT") or ""
    if not host or not port:
        raise RuntimeError(_NO_TARGET)
    return {"host": host, "port": int(port),
            "user": os.getenv("PG_USER", "cfdb"),
            "password": os.getenv("PG_PASSWORD", "cfdb"),
            "dbname": os.getenv("PG_DB", "cfdb")}


def get_conn():
    return psycopg2.connect(**pg_params())


def payload_row_count(payload) -> int:
    """How many records a landed response actually carried.

    Captured at load time so "CFBD returned 200 with nothing in it" is a fact in the
    warehouse rather than something a person has to notice. A 200 with an empty array is
    the failure mode that reports green.
    """
    if not isinstance(payload, dict):
        return 0
    data = payload.get("data")
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return 1 if data else 0
    return 0


RAW_SCHEMA = os.getenv("PG_RAW_SCHEMA", "raw")
MANIFEST_TABLE = f"{RAW_SCHEMA}.raw_manifest"


def _ensure_manifest_table(cur):
    """One row per landed response across every endpoint — the spine for freshness."""
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MANIFEST_TABLE} (
            endpoint text NOT NULL,
            filename text NOT NULL,
            params jsonb,
            status_code int,
            row_count int,
            fetched_at timestamptz,
            loaded_at timestamptz,
            PRIMARY KEY (endpoint, filename)
        );
        """
    )


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

    table = f"{RAW_SCHEMA}.raw_{endpoint}"
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # SCHEMA FIRST. This used to run after the CREATE TABLE below, which works on
            # every machine where the schema already exists and fails on every machine
            # where it does not — so it worked for months and then failed on the first
            # genuinely fresh warehouse, during the move to the droplet. All 66 endpoints
            # errored with `schema "raw" does not exist`.
            #
            # It is the disaster-recovery path that was broken: rebuilding from raw files
            # into a new database is the thing this loader exists to make possible.
            _ensure_manifest_table(cur)
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
                params_json = json.dumps(params) if params is not None else None
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
                    (p.name, json.dumps(payload), status_code, params_json,
                     fetched_at.get(p.name)),
                )
                cur.execute(
                    f"""
                    INSERT INTO {MANIFEST_TABLE}
                        (endpoint, filename, params, status_code, row_count,
                         fetched_at, loaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (endpoint, filename) DO UPDATE SET
                        params = EXCLUDED.params,
                        status_code = EXCLUDED.status_code,
                        row_count = EXCLUDED.row_count,
                        fetched_at = EXCLUDED.fetched_at,
                        loaded_at = EXCLUDED.loaded_at;
                    """,
                    (endpoint, p.name, params_json, status_code,
                     payload_row_count(payload), fetched_at.get(p.name)),
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
