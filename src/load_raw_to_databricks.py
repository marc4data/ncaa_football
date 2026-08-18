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
from typing import Dict, List, Optional, Tuple

from databricks import sql
from dotenv import load_dotenv

from .load_raw_to_postgres import payload_row_count

load_dotenv()

CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
# The loader owns the raw layer only; dbt writes staging and marts.
SCHEMA = os.getenv("DATABRICKS_RAW_SCHEMA", "raw")

# A SQL warehouse round trip dominates; batching is what makes this finish. The batch is
# bounded by *bytes*, not row count: 25 files of 5 MB each is 125 MB of query text, which
# blows the same limit the chunking exists to respect. Row-count batching worked fine until
# it met an endpoint whose files were individually small enough to skip chunking and
# collectively far too big to send.
BATCH_ROWS = 25
BATCH_BYTES = 6_000_000

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


def _size_bounded_batches(paths: List[Path]) -> List[List[Path]]:
    """Group files so no single statement approaches the query-text limit."""
    batches, current, current_bytes = [], [], 0
    for path in paths:
        size = path.stat().st_size
        if current and (current_bytes + size > BATCH_BYTES or len(current) >= BATCH_ROWS):
            batches.append(current)
            current, current_bytes = [], 0
        current.append(path)
        current_bytes += size
    if current:
        batches.append(current)
    return batches


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


def already_loaded(cursor, endpoint: str) -> set:
    """Filenames already landed for this endpoint.

    Makes the load *resumable*, not merely idempotent. MERGE meant a rerun produced the
    right answer, but redid every megabyte to get there — so a failure four hours in cost
    four hours to retry. A 1.7 GB load over a serverless warehouse will be interrupted;
    the question is only whether that is expensive.
    """
    try:
        cursor.execute(f"""
            SELECT filename FROM {CATALOG}.{SCHEMA}.raw_manifest
            WHERE endpoint = {_sql_string(endpoint)}
        """)
        return {row.filename for row in cursor.fetchall()}
    except Exception:
        return set()


def load_endpoint(cursor, endpoint: str, seasons: Optional[List[str]] = None,
                  resume: bool = True) -> int:
    files = raw_files(endpoint, seasons)
    if not files:
        print(f"No files to load for {endpoint}")
        return 0

    if resume:
        done = already_loaded(cursor, endpoint)
        skipped = [f for f in files if f.name in done]
        files = [f for f in files if f.name not in done]
        if skipped:
            print(f"  {endpoint}: skipping {len(skipped)} already loaded")
        if not files:
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

    for batch in _size_bounded_batches(normal):
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


def all_endpoints() -> List[str]:
    """Every endpoint directory present under data/raw."""
    base = Path("data") / "raw"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def pending_by_endpoint(cursor, endpoints: List[str]) -> Dict[str, int]:
    """How many local raw files each endpoint still owes Databricks.

    One query across the whole manifest, not one per endpoint. `load_endpoints` below opens
    a fresh connection per endpoint on purpose — a session held open across a long load is
    what died mid-file once — but paying that cost only to discover an endpoint has nothing
    to do is pure waste, and on a serverless warehouse that startup dominates the cost of a
    daily sync where most endpoints are idle.
    """
    loaded: Dict[str, set] = {}
    try:
        cursor.execute(f"SELECT endpoint, filename FROM {CATALOG}.{SCHEMA}.raw_manifest")
        for row in cursor.fetchall():
            loaded.setdefault(row.endpoint, set()).add(row.filename)
    except Exception:
        # No manifest yet means nothing has ever loaded, so everything is pending. Guessing
        # the opposite would silently skip the very first sync.
        loaded = {}

    pending = {}
    for endpoint in endpoints:
        missing = {p.name for p in raw_files(endpoint)} - loaded.get(endpoint, set())
        if missing:
            pending[endpoint] = len(missing)
    return pending


def load_endpoints(endpoints: List[str],
                   seasons: Optional[List[str]] = None) -> Tuple[int, List[str]]:
    """Load each endpoint, one short-lived connection at a time, three attempts each.

    One connection per endpoint rather than one for the whole run: a single session held
    open for hours against a serverless warehouse is what died last time, mid-file.
    """
    failed: List[str] = []
    total = 0
    for endpoint in endpoints:
        for attempt in (1, 2, 3):
            try:
                with connect() as connection:
                    with connection.cursor() as cursor:
                        _ensure_schema(cursor)
                        total += load_endpoint(cursor, endpoint, seasons)
                break
            except Exception as exc:
                print(f"  {endpoint}: attempt {attempt} failed — {type(exc).__name__}: "
                      f"{str(exc)[:120]}")
                if attempt == 3:
                    failed.append(endpoint)
    return total, failed


def sync(endpoints: List[str], seasons: Optional[List[str]] = None) -> dict:
    """Bring Databricks level with the local raw layer for these endpoints.

    Deliberately additive and idempotent: it loads the files Databricks lacks and touches
    nothing else, so running it twice — or running it after a manual load — costs one query
    and changes nothing. That is what lets it sit on a schedule without supervision.
    """
    with connect() as connection:
        with connection.cursor() as cursor:
            _ensure_schema(cursor)
            pending = pending_by_endpoint(cursor, endpoints)

    if not pending:
        return {"checked": len(endpoints), "pending_endpoints": 0, "loaded": 0, "failed": []}

    print(f"Pending: {', '.join(f'{e}={n}' for e, n in sorted(pending.items()))}")
    total, failed = load_endpoints(sorted(pending), seasons)
    return {"checked": len(endpoints), "pending_endpoints": len(pending),
            "loaded": total, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Load raw CFBD responses into Databricks.")
    parser.add_argument("endpoints", nargs="*", help="endpoint directory names")
    parser.add_argument("--all", action="store_true", help="every endpoint under data/raw")
    parser.add_argument("--seasons", nargs="+", help="restrict to these seasons")
    args = parser.parse_args()

    if args.all:
        endpoints = all_endpoints()
    elif args.endpoints:
        endpoints = args.endpoints
    else:
        parser.print_help()
        return 1

    total, failed = load_endpoints(endpoints, args.seasons)

    print(f"\nLoaded {total} file(s) into {CATALOG}.{SCHEMA}")
    if failed:
        # Loud and non-zero: a partial load must not read as a success.
        print(f"FAILED endpoints ({len(failed)}): {', '.join(failed)}")
        return 1
    return 0


def _ensure_schema(cursor) -> None:
    """Schema and the manifest spine, created before any endpoint is loaded."""
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


if __name__ == "__main__":
    sys.exit(main())
