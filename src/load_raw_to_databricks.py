"""Land raw CFBD responses into Databricks Delta tables.

The Databricks half of the raw layer, mirroring `src/load_raw_to_postgres.py`. Same
contract: one row per raw file, the response stored whole, loads idempotent on filename.

Two differences that matter, both consequences of the platform rather than choices:

1. **JSON is stored as STRING, not a JSON type.** Delta has no `jsonb`. This is precisely
   why the dbt macros dispatch — `get_json_object` reads a string, `->>` reads jsonb — and
   why the Spark implementations had to exist before this loader was worth writing.
2. **Rows go in batched, not one statement per file.** A SQL warehouse round trip is far
   more expensive than a local Postgres one, so files are chunked into multi-row inserts.

Usage:
  python -m src.load_raw_to_databricks teams
  python -m src.load_raw_to_databricks --all
  python -m src.load_raw_to_databricks games --seasons 2024 2025 2026
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from databricks import sql
from dotenv import load_dotenv

from .load_raw_to_postgres import payload_row_count

load_dotenv()

CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "cfdb")

# A SQL warehouse round trip dominates; batching is what makes this finish.
BATCH_ROWS = 25

# Databricks rejects query text over a limit measured empirically at 16 MB OK / 32 MB
# failing ("Query text size exceeds limit"). JSON escaping inflates content on the way
# into a literal, so oversized files are split well under that and reassembled in SQL.
#
# Chunking exists because the Files API — the clean path, volume upload + COPY INTO — is
# refused by the current token: "does not have required scopes: files". A token with the
# files scope would make this unnecessary; see README.
MAX_LITERAL_BYTES = 6_000_000
CHUNK_BYTES = 4_000_000


def connect():
    missing = [k for k in ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH",
                           "DATABRICKS_TOKEN") if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing Databricks settings in .env: {', '.join(missing)}")
    return sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def _sql_string(value: Optional[str]) -> str:
    """A SQL string literal, or NULL. Backslashes matter: Spark treats them as escapes."""
    if value is None:
        return "NULL"
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def raw_files(endpoint: str, seasons: Optional[List[str]] = None) -> List[Path]:
    base = Path("data") / "raw" / endpoint
    if not base.exists():
        return []
    files = sorted(p for p in base.iterdir()
                   if p.suffix == ".json" and p.name != "manifest.json")
    if not seasons:
        return files

    kept = []
    for path in files:
        try:
            params = json.loads(path.read_text(encoding="utf-8")).get("params") or {}
        except json.JSONDecodeError:
            continue
        if str(params.get("year")) in seasons:
            kept.append(path)
    return kept


def fetched_at_index(endpoint: str) -> Dict[str, str]:
    manifest = Path("data") / "raw" / endpoint / "manifest.json"
    if not manifest.exists():
        return {}
    try:
        return {e["filename"]: e.get("added_at")
                for e in json.loads(manifest.read_text(encoding="utf-8"))}
    except json.JSONDecodeError:
        return {}


def _load_large_file(cursor, table: str, endpoint: str, path: Path, payload: dict,
                     fetched_at_value: Optional[str]) -> None:
    """Land one file too big for a single statement, via chunk staging + SQL concat."""
    content = json.dumps(payload)
    params = payload.get("params") if isinstance(payload, dict) else None
    chunks = [content[i:i + CHUNK_BYTES] for i in range(0, len(content), CHUNK_BYTES)]

    staging = f"{CATALOG}.{SCHEMA}._chunk_staging"
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {staging}
        (filename STRING, seq INT, chunk STRING) USING DELTA
    """)
    cursor.execute(f"DELETE FROM {staging} WHERE filename = {_sql_string(path.name)}")
    for seq, chunk in enumerate(chunks):
        cursor.execute(
            f"INSERT INTO {staging} VALUES ({_sql_string(path.name)}, {seq}, "
            f"{_sql_string(chunk)})")

    # array_sort orders the structs by their first field, so the pieces reassemble in the
    # order they were split — concat_ws over collect_list alone would not guarantee that.
    cursor.execute(f"""
        MERGE INTO {table} AS t
        USING (
            SELECT
                filename,
                array_join(transform(array_sort(collect_list(struct(seq, chunk))),
                                     s -> s.chunk), '') AS content,
                {payload.get('status_code') if isinstance(payload, dict) else 'NULL'} AS status_code,
                {_sql_string(json.dumps(params) if params is not None else None)} AS params,
                {payload_row_count(payload)} AS row_count,
                {_sql_string(fetched_at_value)} AS fetched_at,
                current_timestamp() AS loaded_at
            FROM {staging}
            WHERE filename = {_sql_string(path.name)}
            GROUP BY filename
        ) AS s
        ON t.filename = s.filename
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    cursor.execute(f"DELETE FROM {staging} WHERE filename = {_sql_string(path.name)}")

    cursor.execute(f"""
        MERGE INTO {CATALOG}.{SCHEMA}.raw_manifest AS t
        USING (SELECT {_sql_string(endpoint)} AS endpoint, {_sql_string(path.name)} AS filename,
                      {_sql_string(json.dumps(params) if params is not None else None)} AS params,
                      {payload.get('status_code') if isinstance(payload, dict) else 'NULL'} AS status_code,
                      {payload_row_count(payload)} AS row_count,
                      {_sql_string(fetched_at_value)} AS fetched_at,
                      current_timestamp() AS loaded_at) AS s
        ON t.endpoint = s.endpoint AND t.filename = s.filename
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)


def load_endpoint(cursor, endpoint: str, seasons: Optional[List[str]] = None) -> int:
    files = raw_files(endpoint, seasons)
    if not files:
        print(f"No files to load for {endpoint}")
        return 0

    table = f"{CATALOG}.{SCHEMA}.raw_{endpoint.replace('/', '_')}"
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            filename STRING NOT NULL,
            content STRING,
            status_code INT,
            params STRING,
            row_count INT,
            fetched_at TIMESTAMP,
            loaded_at TIMESTAMP
        ) USING DELTA
    """)

    fetched_at = fetched_at_index(endpoint)
    loaded = 0

    # Oversized files take the chunked path; the rest batch normally.
    large = [p for p in files if p.stat().st_size > MAX_LITERAL_BYTES]
    normal = [p for p in files if p.stat().st_size <= MAX_LITERAL_BYTES]

    for path in large:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        _load_large_file(cursor, table, endpoint, path, payload, fetched_at.get(path.name))
        loaded += 1
        print(f"  {endpoint}: {loaded}/{len(files)} (chunked {path.stat().st_size/1e6:.0f} MB)")

    for start in range(0, len(normal), BATCH_ROWS):
        batch = normal[start:start + BATCH_ROWS]
        values = []
        for path in batch:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            params = payload.get("params") if isinstance(payload, dict) else None
            values.append(
                f"({_sql_string(path.name)}, {_sql_string(json.dumps(payload))}, "
                f"{payload.get('status_code') if isinstance(payload, dict) else 'NULL'}, "
                f"{_sql_string(json.dumps(params) if params is not None else None)}, "
                f"{payload_row_count(payload)}, "
                f"{_sql_string(fetched_at.get(path.name))}, current_timestamp())"
            )
        if not values:
            continue

        # MERGE keeps the load idempotent on filename, matching the Postgres upsert.
        cursor.execute(f"""
            MERGE INTO {table} AS t
            USING (
                SELECT * FROM VALUES {', '.join(values)}
                AS s(filename, content, status_code, params, row_count, fetched_at, loaded_at)
            ) AS s
            ON t.filename = s.filename
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
        # The manifest spine, same as Postgres: one row per response across all endpoints,
        # so freshness and empty-response detection work identically on both engines.
        manifest_values = [
            f"({_sql_string(endpoint)}, " + v.lstrip("(")
            for v in values
        ]
        cursor.execute(f"""
            MERGE INTO {CATALOG}.{SCHEMA}.raw_manifest AS t
            USING (
                SELECT * FROM VALUES {', '.join(manifest_values)}
                AS s(endpoint, filename, content, status_code, params, row_count,
                     fetched_at, loaded_at)
            ) AS s
            ON t.endpoint = s.endpoint AND t.filename = s.filename
            WHEN MATCHED THEN UPDATE SET
                params = s.params, status_code = s.status_code, row_count = s.row_count,
                fetched_at = s.fetched_at, loaded_at = s.loaded_at
            WHEN NOT MATCHED THEN INSERT
                (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at)
                VALUES (s.endpoint, s.filename, s.params, s.status_code, s.row_count,
                        s.fetched_at, s.loaded_at)
        """)

        loaded += len(values)
        print(f"  {endpoint}: {loaded}/{len(files)}")

    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Load raw CFBD responses into Databricks.")
    parser.add_argument("endpoints", nargs="*", help="endpoint directory names")
    parser.add_argument("--all", action="store_true", help="every endpoint under data/raw")
    parser.add_argument("--seasons", nargs="+", help="restrict to these seasons")
    args = parser.parse_args()

    if args.all:
        base = Path("data") / "raw"
        endpoints = sorted(p.name for p in base.iterdir() if p.is_dir())
    elif args.endpoints:
        endpoints = args.endpoints
    else:
        parser.print_help()
        return 1

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_manifest (
                    endpoint STRING NOT NULL,
                    filename STRING NOT NULL,
                    params STRING,
                    status_code INT,
                    row_count INT,
                    fetched_at TIMESTAMP,
                    loaded_at TIMESTAMP
                ) USING DELTA
            """)
            total = sum(load_endpoint(cursor, e, args.seasons) for e in endpoints)

    print(f"\nLoaded {total} file(s) into {CATALOG}.{SCHEMA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
