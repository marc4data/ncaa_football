"""Prove the pipeline ran. Silence is not success.

WHY THIS EXISTS. The laptop stack was down from 24 to 28 August and nobody noticed for four
days. Every alert this project had was of the form "something ran and failed" — and nothing
ran, so nothing failed, so nothing alerted. Four days of a dead pipeline looked exactly like
four quiet days.

Alerting cannot fire when nothing runs. The only construction that catches a stopped pipeline
is the inverse: the pipeline states that it is alive on a known cadence, and something
OUTSIDE it complains when that statement stops arriving.

TWO SINKS, AND BOTH MATTER FOR DIFFERENT REASONS.

  the warehouse   an ops table, so "when did each DAG last succeed" is queryable, joins to
                  the rest of the telemetry, and survives the external service being
                  unreachable. It cannot raise an alarm on its own — a table nobody reads
                  while the box is off is exactly the failure we are fixing.

  a ping URL      an HTTP GET to an external monitor. That monitor is the only component
                  that can notice ABSENCE, because it is the only one still running when
                  the droplet is not.

ON SUCCESS ONLY, WHICH IS THE WHOLE POINT. A heartbeat emitted from a failed run is a lie —
it says the pipeline is healthy at the exact moment it is not. Every call site is wired to a
task that runs only when its upstream succeeded, and nothing here catches an exception on
behalf of a caller: if the work failed, this must not be reached.

A FAILURE TO PING IS NOT A FAILURE OF THE RUN. The reverse — letting a monitor outage fail a
green pipeline — would make the safety net the most fragile part of the system. Ping errors
are logged and swallowed; the warehouse row is written first, so the record survives either
way.
"""
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# Short. A heartbeat that hangs delays the DAG it is reporting on, and a monitor that cannot
# be reached in ten seconds is not going to be reached in sixty.
PING_TIMEOUT_SECONDS = 10

# Environment holds one ping URL per monitored cadence, so silencing one is a config change
# rather than a code change — which is how the required "silence it and show the alert"
# test is run without editing a DAG.
PING_ENV_PREFIX = "CFDB_HEARTBEAT_URL_"

TABLE = "ops.pipeline_heartbeat"


def ping_url_for(name: str) -> Optional[str]:
    """The configured monitor URL for one cadence, or None if it has none."""
    return os.getenv(PING_ENV_PREFIX + name.upper().replace("-", "_").replace(".", "_"))


def _ensure_table(cursor) -> None:
    cursor.execute("create schema if not exists ops")
    cursor.execute(f"""
        create table if not exists {TABLE} (
            heartbeat_name text not null,
            dag_id         text,
            run_id         text,
            beat_at        timestamptz not null,
            primary key (heartbeat_name, beat_at)
        )
    """)


def record(name: str, dag_id: str = "", run_id: str = "",
           beat_at: Optional[datetime] = None) -> datetime:
    """Write the heartbeat to the warehouse. Raises if the warehouse is unreachable.

    This one DOES raise. A pipeline that cannot write to its own warehouse has not
    succeeded, whatever the upstream tasks reported, and hiding that would be the same
    class of lie as beating on failure.
    """
    import psycopg2
    # One place resolves the warehouse target, and one place refuses a default that
    # cannot work (R-312). Rolling our own getenv here is how it drifted before.
    from .load_raw_to_postgres import pg_params

    beat_at = beat_at or datetime.now(timezone.utc)
    connection = psycopg2.connect(
        connect_timeout=10, **pg_params())
    try:
        with connection, connection.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute(
                f"insert into {TABLE} (heartbeat_name, dag_id, run_id, beat_at) "
                f"values (%s, %s, %s, %s) on conflict do nothing",
                (name, dag_id, run_id, beat_at))
    finally:
        connection.close()
    return beat_at


def ping(name: str) -> bool:
    """Tell the external monitor this cadence is alive. Never raises.

    Returns True if a ping was sent and accepted. False covers both "no URL configured" and
    "the monitor could not be reached" — deliberately not distinguished by the return value,
    because neither is the caller's problem to handle. Both are printed.
    """
    url = ping_url_for(name)
    if not url:
        print(f"heartbeat: no monitor configured for {name!r} "
              f"({PING_ENV_PREFIX}{name.upper()} unset) — warehouse row written, "
              f"nothing is watching for absence")
        return False
    try:
        with urllib.request.urlopen(url, timeout=PING_TIMEOUT_SECONDS) as response:
            print(f"heartbeat: pinged {name} -> HTTP {response.status}")
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError) as error:
        # Swallowed on purpose. See the module docstring: a monitor outage must not fail a
        # green pipeline, or the safety net becomes the most fragile component.
        print(f"heartbeat: ping to {name} FAILED ({type(error).__name__}: {error}) — "
              f"the run succeeded and the warehouse row is written")
        return False


def beat(name: str, dag_id: str = "", run_id: str = "") -> datetime:
    """Record then ping. The order matters: the durable record is never lost to a flaky GET."""
    beat_at = record(name, dag_id=dag_id, run_id=run_id)
    ping(name)
    return beat_at


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="the cadence being reported, e.g. weekly_results")
    parser.add_argument("--dag-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--check", action="store_true",
                        help="report which cadences have a monitor configured, and exit")
    args = parser.parse_args(argv)

    if args.check:
        configured = ping_url_for(args.name)
        print(f"{args.name}: {'configured' if configured else 'NO MONITOR CONFIGURED'}")
        return 0 if configured else 1

    beat_at = beat(args.name, dag_id=args.dag_id, run_id=args.run_id)
    print(f"heartbeat: {args.name} at {beat_at.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
