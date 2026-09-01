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
import gzip
import os
import subprocess
import sys
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# See deploy/README.md. No literal host in a tracked file.
DROPLET = os.getenv("SERVING_SSH_HOST", "")
STACK_DIR = "/opt/cfdb"

# The restricted publish identity. A dedicated Unix user with a forced command, no shell,
# and NO DOCKER GROUP — the last one is the point. `docker compose exec` was how this job
# reached Postgres, and Docker socket access is root by construction: `docker run -v /:/host`
# and you own the box. A "restricted" user in the docker group would have been theatre.
#
# Postgres is bound to 127.0.0.1:5433 on the droplet, so this identity reaches it with psql
# and nothing else. Its blast radius is the serving database, which is what publishing is.
#
# The key is passed by path and never read into this process. Airflow mounts it read-only;
# it is not in the repository and does not appear in a task log.
PUBLISH_HOST = os.getenv("SERVING_PUBLISH_HOST", "")
PUBLISH_KEY = os.getenv("SERVING_PUBLISH_KEY", "")
READ_ROLE = os.getenv("CFDB_READ_USER", "cfdb_read")


def _use_restricted() -> bool:
    """Use the restricted key when one is configured, the root path otherwise.

    Both transports are kept during the changeover on purpose: the root path is what has
    been publishing successfully for weeks, and switching a working production job with six
    days to the season on the strength of one green run is how the changeover becomes the
    incident.
    """
    return bool(PUBLISH_KEY)


# How long one publish verb may run before we give up on it.
#
# A HANGING RESTORE IS THE WORST CASE, so it gets a bound. On 29 August the 20:00 restore ran
# for 34 minutes before the worker was killed — long past Airflow's task-heartbeat timeout, so
# it died without a traceback, and the retry did not start until the ten-minute retry delay
# had also elapsed. A healthy restore of the same 333 MB dump takes two to ten minutes.
#
# Failing at twelve turns a 46-minute outage into a prompt, retryable error, and the retry is
# where recovery actually comes from. Paired with --single-transaction on the remote, a
# timeout now rolls back rather than leaving the site holding empty tables.
PUBLISH_TIMEOUT_SECONDS = int(os.getenv("SERVING_PUBLISH_TIMEOUT", "720"))

# The cheap verbs answer in seconds; only the restore streams a dump.
QUICK_VERB_TIMEOUT_SECONDS = 120

# gzip level for the dump. 6 is the default and the right trade here: level 9 spends roughly
# three times the CPU to save another few percent of a link that is already 5.6x quieter.
COMPRESS_LEVEL = 6


def _publish_ssh(verb: str, *, stdin: bytes = b"") -> subprocess.CompletedProcess:
    """Invoke one verb of the forced command. The remote side chooses nothing."""
    timeout = PUBLISH_TIMEOUT_SECONDS if stdin else QUICK_VERB_TIMEOUT_SECONDS
    try:
        return subprocess.run(
            ["ssh", "-i", PUBLISH_KEY, "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=accept-new", PUBLISH_HOST, verb],
            input=stdin, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Raised, not returned: a timed-out publish must fail the task so the retry runs.
        # Returning a non-zero result would be indistinguishable from a remote refusal, and
        # the distinction is what tells you whether to look at the droplet or the network.
        raise RuntimeError(
            f"publish verb '{verb.split()[0]}' timed out after {timeout}s. The remote "
            f"restore runs in one transaction, so the serving database has rolled back to "
            f"the previous good data rather than being left empty.")


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
    "srv_team_rating",
    "srv_data_dictionary",
    "srv_game_weather",
]

# THE PLAYER TABLES PUBLISH ON A SLOWER CADENCE, AND THE REASON IS THE WIRE.
#
# These three are 608 MB of the serving schema's 932 MB. Including them takes a publish from
# 59 MB to 182 MB gzipped — and the scores DAG publishes the whole serving schema EVERY TWO
# HOURS over a link that is already this pipeline's failure point. 59 MB has taken 13 to 17
# minutes when that link is busy, long enough for Airflow to disown the task as a zombie and
# kill it mid-stream; on 29 August that left the site serving nothing for 46 minutes on a
# game day. Tripling the payload would make that routine rather than occasional.
#
# Splitting is honest rather than merely cheap: player season totals, box scores and play
# attributions change when games are played, not every two hours. The scores DAG exists to
# move scores and lines quickly, and none of these three are that.
#
# Selective publishing needs no change to the fragile part. publish_schema already takes an
# explicit table list, and the dump carries --clean --if-exists, which drops only the tables
# IN the dump — so a hot publish leaves these three untouched rather than deleting them.
HEAVY_SERVING = [
    "srv_player_stats",
    "srv_player_game_log",
    "srv_player_play",
]

# What the two-hourly publish ships: everything except the heavy three. Measured at 324 MB,
# which is exactly what it was before the player tables existed.
HOT_SERVING = [t for t in DEFAULT_SERVING if t not in HEAVY_SERVING]

# What a full publish ships. DEFAULT_SERVING stays the complete list so nothing that asks
# for "everything" silently gets a subset.
DEFAULT_SERVING = DEFAULT_SERVING + HEAVY_SERVING


def local_pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("PG_PASSWORD", "cfdb")
    return env


def _direct_pg() -> bool:
    """Whether to reach the transform warehouse directly rather than through Docker.

    Airflow has no Docker socket and must not be given one — socket access is root on the
    host. Inside the compose network it reaches Postgres by service name, so when PG_HOST
    is set this takes the direct route and the Docker path is only used from a laptop.
    """
    return bool(os.getenv("PG_HOST"))


def _pg_dump_binary() -> str:
    """A pg_dump no newer than the server being restored INTO.

    pg_dump 18 emits `SET transaction_timeout = 0`, a parameter added in Postgres 17, and a
    15 server rejects the whole restore with `unrecognized configuration parameter`. The
    direction matters: a newer client may dump FROM an older server, but the output is not
    guaranteed to load INTO one.

    The version is asked of the server rather than hardcoded, so upgrading the warehouse
    does not leave this silently pinned to a client that no longer matches.
    """
    override = os.getenv("PG_DUMP_BINARY")
    if override:
        return override
    try:
        probe = subprocess.run(
            ["psql"] + _local_psql_args() + ["-tAc", "show server_version_num"],
            capture_output=True, env=local_pg_env(), timeout=30)
        major = int(probe.stdout.decode().strip()) // 10000
    except Exception:                                              # noqa: BLE001
        return "pg_dump"
    versioned = f"/usr/lib/postgresql/{major}/bin/pg_dump"
    return versioned if os.path.exists(versioned) else "pg_dump"


def _local_psql_args() -> List[str]:
    return ["-h", os.getenv("PG_HOST", "localhost"),
            "-p", os.getenv("PG_PORT", "5432"),
            "-U", os.getenv("PG_USER", "cfdb"),
            "-d", os.getenv("PG_DB", "cfdb")]


def dump_marts(marts: List[str], schema: str = MARTS_SCHEMA) -> bytes:
    """pg_dump the named tables from one schema of the transform warehouse."""
    table_args = []
    for mart in marts:
        table_args += ["-t", f"{schema}.{mart}"]

    flags = ["--clean", "--if-exists", "--no-owner", "--no-privileges"]
    if _direct_pg():
        command = [_pg_dump_binary()] + _local_psql_args() + flags + table_args
    else:
        command = [
            "docker", "compose", "exec", "-T", "postgres",
            "pg_dump", "-U", os.getenv("PG_USER", "cfdb"),
            "-d", os.getenv("PG_DB", "cfdb"),
        ] + flags + table_args

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
    """Stream the dump into the serving database over SSH."""
    # pg_dump -t emits no CREATE SCHEMA, so the target schema has to exist first.
    if _use_restricted():
        for verb in (f"ensure-schema {schema}", ):
            result = _publish_ssh(verb)
            if result.returncode != 0:
                raise RuntimeError(f"{verb} failed: {result.stderr.decode()[:400]}")
        # COMPRESS, BECAUSE THE WIRE IS THE BOTTLENECK AND THE WIRE IS WHAT FAILS.
        #
        # Measured: the dump is 334 MB, the link to the droplet runs at about 20 Mbit/s, and
        # a healthy publish takes 135 seconds — which is, to within a few seconds, exactly
        # the time needed to upload 334 MB at that rate. The database work is not the cost;
        # the upload is essentially all of it.
        #
        # That is why this job is fragile. When the link is busy the same publish takes 13 to
        # 17 minutes, which is long enough for Airflow to disown the task as a zombie and
        # kill it mid-stream. Postgres then logs a truncated COPY at a different random line
        # every time, which reads like data corruption and is really just a severed pipe.
        #
        # gzip -6 costs about four seconds of CPU and takes 334 MB to 59 MB. Same bytes land,
        # same single transaction wraps them; the window that was failing gets 5.6x smaller.
        payload = gzip.compress(dump, COMPRESS_LEVEL)
        print(f"  compressed to {len(payload) / 1e6:.1f} MB "
              f"({len(dump) / max(len(payload), 1):.1f}x) for transfer")
        result = _publish_ssh(f"restore-gz {schema}", stdin=payload)
        if result.returncode != 0:
            raise RuntimeError(f"restore failed: {result.stderr.decode()[:400]}")
        return

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
    if _use_restricted():
        result = _publish_ssh(f"grant {schema} {READ_ROLE}")
        if result.returncode != 0:
            raise RuntimeError(f"grant failed: {result.stderr.decode()[:400]}")
        return

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
        count_sql = f"select count(*) from {schema}.{mart}"
        if _direct_pg():
            local_cmd = ["psql"] + _local_psql_args() + ["-tAc", count_sql]
        else:
            local_cmd = ["docker", "compose", "exec", "-T", "postgres", "psql", "-U",
                         os.getenv("PG_USER", "cfdb"), "-d", os.getenv("PG_DB", "cfdb"),
                         "-tAc", count_sql]
        local = subprocess.run(local_cmd, capture_output=True, env=local_pg_env())
        if _use_restricted():
            remote = _publish_ssh(f"count {schema} {mart}")
        else:
            remote = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", DROPLET,
                 f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
                 f'docker compose exec -T postgres psql -tAc '
                 f'"select count(*) from {schema}.{mart}" '
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


def publish_all(schemas: Optional[List[str]] = None, hot: bool = False) -> dict:
    """Publish every contracted schema. The entry point Airflow calls.

    Returns a summary rather than printing only, so a task log carries the row counts that
    were verified. `verify` raises on any mismatch, so a green task means every table was
    counted on both sides and agreed — this is the last hop before a user sees data and,
    until it was scheduled, the only hop with no check on it at all.

    `hot=True` publishes only the fast-moving serving views, which is what the two-hourly
    scores refresh wants: the three player tables are 608 MB of the schema and change when
    games are played, not every two hours. See HEAVY_SERVING.
    """
    schemas = schemas or ["marts", "serving"]
    published = {}
    for schema in schemas:
        if schema == SERVING_SCHEMA:
            # `hot` ships only the fast-moving views; see HEAVY_SERVING for why. The default
            # stays the full list, so a caller that says nothing still gets everything.
            tables = HOT_SERVING if hot else DEFAULT_SERVING
        else:
            tables = DEFAULT_MARTS
        publish_schema(tables, schema)
        published[schema] = len(tables)
    transport = "restricted publish key" if _use_restricted() else "root ssh"
    print(f"Published via {transport}: "
          + ", ".join(f"{k}={v} table(s)" for k, v in published.items()))
    return {"schemas": published, "transport": transport}


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
