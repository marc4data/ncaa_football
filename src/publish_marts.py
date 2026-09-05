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
import contextlib
import getpass
import socket
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
    "srv_game",
    "srv_game_team",
    "srv_standings",
    "srv_teams_index",
    "srv_team_overview",
    "srv_team_game_log",
    "srv_rankings",
    "srv_rankings_compare",
    "srv_team_stats",
    "srv_odds_board",
    "srv_edge_finder",
    "srv_model_performance",
    "srv_line_movement",
    "srv_system_health",
    "srv_team_rating",
    "srv_data_dictionary",
    "srv_game_weather",
    # The weekly distributions. Small — one row per week per metric per day, and ten bin rows
    # under it — so they ride the hot publish rather than the weekly one: the numbers move
    # every time a line moves, and a week-old distribution on a live page is worse than none.
    "srv_week_metric_distribution",
    "srv_week_metric_distribution_bin",
    "srv_team_roster",
    "srv_game_travel",
    "srv_edge_bucket_performance",
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


# RETIRED 2026-09-05 (R-312). _direct_pg() used to choose between a direct psql/pg_dump and
# `docker compose exec -T postgres` — the second being the LAPTOP's local Postgres, which was
# decommissioned with the rest of the local stack (R-296). There is nothing on the other side
# of that branch any more.
#
# It is gone rather than left returning True, because a dead branch that still reads like a
# supported path is how somebody concludes the laptop route is available. Both callers now
# take the direct route unconditionally: Airflow reaches the warehouse by compose service
# name, a laptop reaches it through scripts/warehouse_tunnel.sh, and pg_params() refuses to
# guess when neither is configured.


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
    # Same source, same refusal as everywhere else — see load_raw_to_postgres (R-312).
    from .load_raw_to_postgres import pg_params
    cfg = pg_params()
    return ["-h", cfg["host"], "-p", str(cfg["port"]),
            "-U", cfg["user"], "-d", cfg["dbname"]]


def dump_marts(marts: List[str], schema: str = MARTS_SCHEMA) -> bytes:
    """pg_dump the named tables from one schema of the transform warehouse."""
    table_args = []
    for mart in marts:
        table_args += ["-t", f"{schema}.{mart}"]

    flags = ["--clean", "--if-exists", "--no-owner", "--no-privileges"]
    command = [_pg_dump_binary()] + _local_psql_args() + flags + table_args

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
        local_cmd = ["psql"] + _local_psql_args() + ["-tAc", count_sql]
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


# ==========================================================================================
# ONE PUBLISH AT A TIME (R-314). A POSTGRES ADVISORY LOCK ON THE WAREHOUSE.
#
# `pg_dump --clean --if-exists` against ONE serving Postgres, callable from every working
# copy and from Airflow. Two publishes overlapping means one dropping tables the other is
# restoring into, and the visible symptom is the site rendering an empty page.
#
# WHY NOT THE DROPLET LOCK scripts/deploy_main.sh USES. That one is a `mkdir` over root SSH.
# This job deliberately does not have root SSH: it goes through a forced-command identity
# with no shell, and "the remote side chooses nothing" is the security property that makes
# the restricted key worth having. Sending it an arbitrary mkdir would give that back.
#
# WHY AN ADVISORY LOCK RATHER THAN A LOCKFILE. It is held by a CONNECTION, so it is released
# when the connection ends — including when the process is killed, which is the case a
# lockfile gets wrong. On 29 August a restore ran 34 minutes and the worker was killed
# without a traceback; a lockfile would have survived that and blocked every retry
# afterwards. There is no stale advisory lock to clear, ever.
#
# The lock lives on the WAREHOUSE because that is the one instance every publisher already
# connects to — Airflow on the compose network, a laptop through the tunnel. The serving
# Postgres would be the more obvious home and is unreachable except through the forced
# command, which is the same reason as above.
#
# IT REFUSES, IT NEVER QUEUES. try_ rather than a blocking lock: a publish that waited would
# start by dumping a warehouse the first publish has since rebuilt, and ship it as current.
# ==========================================================================================
# Arbitrary but fixed. Advisory lock keys are a global namespace on the instance, so this is
# recorded here rather than computed, and changing it silently disables the lock.
PUBLISH_LOCK_KEY = 8_140_927_318


@contextlib.contextmanager
def publish_lock():
    """Hold the publish lock for the duration of the block, or refuse and say who holds it."""
    from .load_raw_to_postgres import get_conn

    connection = get_conn()
    connection.autocommit = True
    holder = f"{getpass.getuser()}@{socket.gethostname()} pid {os.getpid()}"
    try:
        with connection.cursor() as cursor:
            cursor.execute("select pg_try_advisory_lock(%s)", (PUBLISH_LOCK_KEY,))
            if not cursor.fetchone()[0]:
                cursor.execute("""
                    select coalesce(a.application_name, ''), a.usename, a.client_addr,
                           a.backend_start
                    from pg_locks l join pg_stat_activity a on a.pid = l.pid
                    where l.locktype = 'advisory' and l.objid = %s and l.granted
                """, (PUBLISH_LOCK_KEY % 2**32,))
                other = cursor.fetchone()
                detail = (f"held by {other[1]}@{other[2] or 'local'} since {other[3]}"
                          if other else "held by a connection this session cannot see")
                raise RuntimeError(
                    f"ANOTHER PUBLISH IS RUNNING — refusing rather than queueing.\n"
                    f"  lock   : advisory {PUBLISH_LOCK_KEY} on the warehouse\n"
                    f"  {detail}\n"
                    f"  this   : {holder}\n\n"
                    f"  A second publish would dump a warehouse the first one has already\n"
                    f"  rebuilt and ship it to the site as current. Wait for it to finish;\n"
                    f"  there is nothing to clear — the lock ends with its connection.")
            # Named so the refusal above can say who, without a table to keep in sync.
            cursor.execute("select set_config('application_name', %s, false)",
                           (f"cfdb_publish {holder}",))
        yield
    finally:
        connection.close()          # releases the advisory lock; no explicit unlock needed


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
    with publish_lock():
        for schema in schemas:
            if schema == SERVING_SCHEMA:
                # `hot` ships only the fast-moving views; see HEAVY_SERVING for why. The
                # default stays the full list, so a caller that says nothing gets everything.
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

    # The same lock publish_all takes. main() is the HAND-RUN path — the one that exists in
    # every working copy — so it is the caller that most needs it, not the one to exempt.
    with publish_lock():
        for tables, schema in plan:
            publish_schema(tables, schema)

    print("\nPublish complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
