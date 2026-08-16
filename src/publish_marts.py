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
DEFAULT_MARTS = [
    "mart_team_schedule",
    "mart_team_season_record",
    "mart_data_freshness",
]


def local_pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("PG_PASSWORD", "cfdb")
    return env


def dump_marts(marts: List[str]) -> bytes:
    """pg_dump the named marts from the transform warehouse."""
    table_args = []
    for mart in marts:
        table_args += ["-t", f"public.{mart}"]

    command = [
        "docker", "compose", "exec", "-T", "postgres",
        "pg_dump", "-U", os.getenv("PG_USER", "cfdb"), "-d", os.getenv("PG_DB", "cfdb"),
        "--clean", "--if-exists", "--no-owner", "--no-privileges",
    ] + table_args

    result = subprocess.run(command, capture_output=True, env=local_pg_env())
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()[:400]}")
    return result.stdout


def restore_to_serving(dump: bytes) -> None:
    """Stream the dump into the serving container over SSH."""
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


def grant_read_access(marts: List[str]) -> None:
    """Re-grant SELECT to the read-only role.

    `--clean` drops and recreates each table, and a recreated table does not inherit the
    old one's grants. Without this the site would break on the first republish with a
    permission error — the kind of failure that looks like a database problem and is
    actually a publish-job problem.
    """
    grants = " ".join(
        f'GRANT SELECT ON public.{m} TO \\"$CFDB_READ_USER\\";' for m in marts
    )
    remote = (
        f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
        f'docker compose exec -T postgres psql -v ON_ERROR_STOP=1 '
        f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB" -c "{grants}"'
    )
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", DROPLET, remote],
                            capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"grant failed: {result.stderr.decode()[:400]}")


def verify(marts: List[str]) -> None:
    """Count rows on both sides and refuse to call a mismatch a success."""
    for mart in marts:
        local = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres", "psql", "-U",
             os.getenv("PG_USER", "cfdb"), "-d", os.getenv("PG_DB", "cfdb"),
             "-tAc", f"select count(*) from {mart}"],
            capture_output=True, env=local_pg_env())
        remote = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", DROPLET,
             f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
             f'docker compose exec -T postgres psql -tAc "select count(*) from {mart}" '
             f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB"'],
            capture_output=True)
        left = local.stdout.decode().strip()
        right = remote.stdout.decode().strip()
        status = "ok" if left == right and left else "MISMATCH"
        print(f"  {mart:28} transform={left:>9} serving={right:>9}  {status}")
        if status == "MISMATCH":
            raise RuntimeError(f"{mart} did not publish cleanly")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish marts to the serving database.")
    parser.add_argument("--marts", nargs="+", default=DEFAULT_MARTS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Publishing {len(args.marts)} mart(s) to {DROPLET}")
    if args.dry_run:
        for mart in args.marts:
            print(f"  would publish {mart}")
        return 0

    dump = dump_marts(args.marts)
    print(f"  dumped {len(dump) / 1e6:.1f} MB")
    restore_to_serving(dump)
    grant_read_access(args.marts)
    print("  restored; verifying")
    verify(args.marts)
    print("Publish complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
