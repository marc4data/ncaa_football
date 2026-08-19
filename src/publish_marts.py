"""Publish marts from the transform warehouse to the serving database (M5).

The serving contract: the site reads marts from serving Postgres and nothing else. This
moves them there.

**Why it goes over SSH rather than a database connection.** The droplet publishes no
ports — the firewall allows SSH only, and Postgres lives on an internal Docker network
where the site reaches it by service name. That is the settled access architecture, not an
oversight, so publishing dials in the one way that is open: `pg_dump` locally, streamed
over SSH, restored inside the container. Nothing about it requires opening a port.

Idempotent by construction: the dump carries `--clean --if-exists`, so a republish
replaces each mart rather than appending to it. Marts are derived data — rebuilding them
is always safe, which is what lets this be a blunt replace instead of a merge.

Source-agnostic by design: today it reads the transform Postgres; after the M4 cutover it
reads Databricks. Same contract, one flag.

Usage:
  python -m src.publish_marts --dry-run
  python -m src.publish_marts
  python -m src.publish_marts --marts mart_team_schedule
"""
import argparse
import os
import subprocess
import sys
from typing import List

from dotenv import load_dotenv

load_dotenv()

DROPLET = os.getenv("SERVING_SSH_HOST", "root@143.110.225.139")
STACK_DIR = "/opt/cfdb"

# The site's contract. Staging views and raw tables deliberately do not travel: serving
# holds what the site reads, so a page cannot accidentally query a 1.7 GB raw table.
MARTS_SCHEMA = "marts"
SERVING_SCHEMA = "serving"

# The legacy contract. Still published so the running site keeps working until it is
# repointed; dropped only after that, per the strangler pattern.
DEFAULT_MARTS = [
    "mart_team_schedule",
    "mart_team_season_record",
    "mart_data_freshness",
]

# The serving contract — what the site reads after the cutover.
#
# srv_data_dictionary is LAST on purpose. It catalogues the serving layer, so publishing it
# before its siblings ships a dictionary describing the previous state. Measured during A1:
# built in DAG order it was 31 columns short of the layer it claimed to describe.
DEFAULT_SERVING = [
    "srv_schedule",
    "srv_scoreboard",
    "srv_standings",
    "srv_teams_index",
    "srv_team_overview",
    "srv_team_game_log",
    "srv_rankings",
    "srv_rankings_compare",
    "srv_team_stats",
    "srv_matchup",
    "srv_today_edges",
    "srv_odds_board",
    "srv_edge_finder",
    "srv_model_performance",
    "srv_line_movement",
    "srv_system_health",
    "srv_data_dictionary",
]


def local_pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("PG_PASSWORD", "cfdb")
    return env


def dump_marts(marts: List[str], schema: str = MARTS_SCHEMA) -> bytes:
    """pg_dump the named tables from one schema of the transform warehouse."""
    table_args = []
    for mart in marts:
        table_args += ["-t", f"{schema}.{mart}"]

    command = [
        "docker", "compose", "exec", "-T", "postgres",
        "pg_dump", "-U", os.getenv("PG_USER", "cfdb"), "-d", os.getenv("PG_DB", "cfdb"),
        "--clean", "--if-exists", "--no-owner", "--no-privileges",
    ] + table_args

    result = subprocess.run(command, capture_output=True, env=local_pg_env())
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()[:400]}")
    return result.stdout


def remote_sql(statement: str) -> None:
    r"""Run one SQL statement on the serving database over SSH.

    Kept separate from the streaming restore on purpose: `docker compose exec -T` consumes
    stdin, so chaining a `-c` call ahead of the dump on the same SSH channel makes the
    first command eat the dump — which surfaces as `invalid command \N`, a COPY-data
    error that says nothing about the actual cause.
    """
    remote = (
        f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
        f'docker compose exec -T postgres psql -v ON_ERROR_STOP=1 '
        f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB" -c "{statement}"'
    )
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", DROPLET, remote],
                            capture_output=True, input=b"")
    if result.returncode != 0:
        raise RuntimeError(f"remote sql failed: {result.stderr.decode()[:400]}")


def restore_to_serving(dump: bytes, schema: str = MARTS_SCHEMA) -> None:
    """Stream the dump into the serving container over SSH."""
    # pg_dump -t emits no CREATE SCHEMA, so the target schema has to exist first.
    remote_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    remote = (
        f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
        'docker compose exec -T postgres psql -v ON_ERROR_STOP=1 '
        '-U "$SERVING_PG_USER" -d "$SERVING_PG_DB"'
    )
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", DROPLET, remote],
        input=dump, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"restore failed: {result.stderr.decode()[:400]}")


def grant_read_access(marts: List[str], schema: str = MARTS_SCHEMA) -> None:
    """Re-grant SELECT to the read-only role.

    `--clean` drops and recreates each table, and a recreated table does not inherit the
    old one's grants. Without this the site would break on the first republish with a
    permission error — the kind of failure that looks like a database problem and is
    actually a publish-job problem.
    """
    # Schema-level, per the layering decision: the serving database contains only marts,
    # so the boundary that matters is "this role cannot see upstream layers" — and a new
    # mart becomes readable on publish rather than needing a grant nobody remembers.
    grants = (
        f'GRANT USAGE ON SCHEMA {schema} TO \\"$CFDB_READ_USER\\"; '
        f'GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO \\"$CFDB_READ_USER\\"; '
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} '
        f'GRANT SELECT ON TABLES TO \\"$CFDB_READ_USER\\";'
    )
    remote_sql(grants)


def verify(marts: List[str], schema: str = MARTS_SCHEMA) -> None:
    """Count rows on both sides and refuse to call a mismatch a success."""
    for mart in marts:
        local = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres", "psql", "-U",
             os.getenv("PG_USER", "cfdb"), "-d", os.getenv("PG_DB", "cfdb"),
             "-tAc", f"select count(*) from {schema}.{mart}"],
            capture_output=True, env=local_pg_env())
        remote = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", DROPLET,
             f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
             f'docker compose exec -T postgres psql -tAc "select count(*) from {schema}.{mart}" '
             f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB"'],
            capture_output=True)
        left = local.stdout.decode().strip()
        right = remote.stdout.decode().strip()
        status = "ok" if left == right and left else "MISMATCH"
        print(f"  {mart:28} transform={left:>9} serving={right:>9}  {status}")
        if status == "MISMATCH":
            raise RuntimeError(f"{mart} did not publish cleanly")


def publish_schema(tables: List[str], schema: str) -> None:
    """Dump, restore, grant and verify one schema."""
    print(f"\n[{schema}] publishing {len(tables)} table(s)")
    dump = dump_marts(tables, schema)
    print(f"  dumped {len(dump) / 1e6:.1f} MB")
    restore_to_serving(dump, schema)
    grant_read_access(tables, schema)
    print("  restored; verifying")
    verify(tables, schema)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish marts to the serving database.")
    parser.add_argument("--marts", nargs="+", default=DEFAULT_MARTS)
    parser.add_argument("--serving", nargs="+", default=DEFAULT_SERVING)
    parser.add_argument("--schemas", nargs="+", default=["marts", "serving"],
                        choices=["marts", "serving"],
                        help="which schemas to publish; both by default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = []
    if "marts" in args.schemas:
        plan.append((args.marts, MARTS_SCHEMA))
    if "serving" in args.schemas:
        plan.append((args.serving, SERVING_SCHEMA))

    print(f"Publishing to {DROPLET}")
    if args.dry_run:
        for tables, schema in plan:
            for t in tables:
                print(f"  would publish {schema}.{t}")
        return 0

    for tables, schema in plan:
        publish_schema(tables, schema)

    print("\nPublish complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
