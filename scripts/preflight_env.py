#!/usr/bin/env python3
"""Say which working copy this is, which profile it is using, and which database that reaches.

WHY THIS EXISTS
---------------
`.gitignore` line 14 is `dbt/profiles.yml` and line 7 is `.env`. The two files that decide
WHICH DATABASE dbt talks to are therefore the two files a `git pull` cannot correct. They are
per working copy and hand-copied, and this repository now has three working copies side by
side (claude_code/, wt-drives/, cfdb_deploy/) with three separate untracked copies, none of
them visible to the others.

That produced the bug this file is the answer to. On 2026-09-05 one working copy's root had
NO dbt/profiles.yml at all while its own worktree had one pointing at `localhost:5432` -- a
Postgres dropped that same day -- and the conclusion drawn was "there is no warehouse to
build against." There is; it is on the droplet. A fix to the template propagates on merge; a
fix to the copy depends on somebody remembering, and a correction that depends on remembering
is not a correction.

So this fails distinctly for the two different mistakes:

    MISSING   no dbt/profiles.yml in this working copy    -> copy it from profiles.yml.example
    WRONG     a profile that names a database that is gone -> the localhost:5432 case

and on success prints one cheap line saying what it resolved, because a wrong target that
connects is the failure mode this project keeps paying for. It does not error; it answers.

SCOPE -- IT MUST NOT FAIL CI, AND IT MUST NOT FAIL AIRFLOW
----------------------------------------------------------
Two committed profiles are correct as they stand and are NOT developer profiles:

    dbt/profiles_ci/profiles.yml        target `ci`      -> localhost, the workflow's
                                                            Postgres service container
    dbt/profiles_airflow/profiles.yml   target `airflow` -> postgres, the compose service

Those target names are exempt by name (MANAGED_TARGETS). Everything else is a developer
profile and is checked strictly -- fail-closed, so a new hand-rolled target is guarded too.
A guard that fires on every green run gets muted, and this project has done exactly that.

Usage
-----
    python scripts/preflight_env.py            # check, print, exit 1 on failure
    python scripts/preflight_env.py --quiet     # print only on failure
    python scripts/preflight_env.py --no-connect  # skip the live probe
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Targets owned by a managed environment, whose hosts are correct as written.
MANAGED_TARGETS = {"ci", "airflow"}

# The dropped database, exactly. Loopback ON THE DEFAULT PORT and nothing else -- see
# _check_host() for why the port is load-bearing rather than decoration.
LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
DEFAULT_PG_PORT = 5432

# What a warehouse looks like from inside. dbt builds these three schemas; a database that
# answers but carries none of them is not the warehouse, whatever the host string says.
WAREHOUSE_SCHEMAS = ("staging", "marts", "serving")

# Keys .env must carry for the pipeline to run. Names only -- values are never read here.
REQUIRED_ENV = ["CFBD_API_KEY", "CFDB_WAREHOUSE_HOST", "CFDB_WAREHOUSE_PORT"]


class PreflightError(RuntimeError):
    """A failure phrased as the thing you have to do about it."""


# ------------------------------------------------------------------------------------------
# Where am I
# ------------------------------------------------------------------------------------------

def working_copy() -> Dict[str, str]:
    """This working copy's path and branch. Printed first because it is the question that
    was never asked: two directories of one repository, in different states, neither visible
    to the other."""
    def git(*args: str) -> str:
        try:
            out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                                 text=True, timeout=15)
            return out.stdout.strip()
        except Exception:                                          # noqa: BLE001
            return ""
    return {"path": str(REPO_ROOT),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)",
            "commit": git("rev-parse", "--short", "HEAD") or "(unknown)"}


def profiles_dir() -> Path:
    """The directory dbt will read profiles.yml from, resolved the way dbt resolves it."""
    override = os.getenv("DBT_PROFILES_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "dbt"


def resolve_profile() -> Tuple[Path, dict]:
    """Load the profile dbt would load, or say precisely which file is missing."""
    directory = profiles_dir()
    path = directory / "profiles.yml"
    if not path.exists():
        raise PreflightError(
            f"NO DEVELOPER PROFILE IN THIS WORKING COPY.\n"
            f"  looked for : {path}\n"
            f"  working copy: {REPO_ROOT}\n\n"
            f"  git cannot fix this for you -- dbt/profiles.yml is gitignored, so it is\n"
            f"  per working copy and hand-copied. Create it:\n\n"
            f"      cp {REPO_ROOT / 'dbt' / 'profiles.yml.example'} {path}\n\n"
            f"  then fill CFDB_WAREHOUSE_HOST and CFDB_WAREHOUSE_PORT in .env."
        )
    import yaml
    with path.open() as handle:
        return path, yaml.safe_load(handle) or {}


def active_target(profile: dict, profile_name: str = "cfdb_profile") -> Tuple[str, dict]:
    """The output dbt would actually use: --target, then DBT_TARGET, then the file's."""
    block = profile.get(profile_name)
    if not block:
        raise PreflightError(f"profiles.yml carries no `{profile_name}:` block")
    name = os.getenv("DBT_TARGET") or block.get("target")
    outputs = block.get("outputs") or {}
    if name not in outputs:
        raise PreflightError(
            f"target {name!r} is not one of the outputs defined in profiles.yml "
            f"({', '.join(sorted(outputs)) or 'none'})")
    return name, outputs[name]


def _render(value) -> str:
    """Resolve the one Jinja form these profiles use: env_var('NAME'[, 'default'])."""
    text = str(value if value is not None else "")
    if "env_var" not in text:
        return text
    import re
    match = re.search(r"env_var\(\s*'([^']+)'\s*(?:,\s*'([^']*)'\s*)?\)", text)
    if not match:
        return text
    name, default = match.group(1), match.group(2)
    resolved = os.getenv(name)
    if resolved is None:
        if default is None:
            # This is the no-fallback case, and it is the point of the no-fallback case.
            raise PreflightError(
                f"{name} is not set, and the profile gives it no fallback -- deliberately.\n"
                f"  Add it to {REPO_ROOT / '.env'} (see .env.example), or export it.")
        return default
    return resolved


# ------------------------------------------------------------------------------------------
# The checks
# ------------------------------------------------------------------------------------------

def _check_host(target_name: str, output: dict) -> Dict[str, str]:
    kind = output.get("type", "postgres")
    if kind != "postgres":
        return {"type": kind, "host": str(output.get("host", "")), "port": "", "dbname": ""}

    host = _render(output.get("host")).strip()
    port_text = _render(output.get("port")).strip() or str(DEFAULT_PG_PORT)
    dbname = _render(output.get("dbname")).strip()
    user = _render(output.get("user")).strip()
    try:
        port = int(port_text)
    except ValueError:
        raise PreflightError(f"port {port_text!r} on target {target_name!r} is not a number")

    if not host:
        raise PreflightError(
            f"target {target_name!r} resolves to an EMPTY host.\n"
            f"  An empty host makes libpq fall back to a unix socket on this machine, which\n"
            f"  is the dropped local Postgres by another name. Set CFDB_WAREHOUSE_HOST.")

    # THE PORT IS LOAD-BEARING HERE, and this is the one judgement call in the file.
    #
    # The obvious rule -- "fail on localhost" -- cannot be the whole rule, because the
    # supported way to reach the warehouse IS a loopback address: an SSH local-forward lands
    # on 127.0.0.1. Host alone cannot tell the good loopback from the bad one.
    #
    # What distinguishes them is the port. `localhost:5432` is the dropped database and
    # nothing else -- it is what the old template said, verbatim, in every copy. A forward
    # is opened on a port chosen not to collide with it. So loopback-on-5432 is refused,
    # loopback-on-anything-else is accepted as a tunnel and SAID OUT LOUD as one, and
    # _probe() then checks that the tunnel actually reaches a warehouse rather than trusting
    # that it does. The port check is the cheap gate; the probe is the real one.
    if host in LOOPBACK and port == DEFAULT_PG_PORT:
        raise PreflightError(
            f"target {target_name!r} points at {host}:{port} -- THE DATABASE THAT WAS "
            f"DROPPED ON 2026-09-05 (R-296).\n"
            f"  This is the stale template. dbt builds in the droplet's warehouse; there is\n"
            f"  no local warehouse and there is not going to be one.\n\n"
            f"  Fix this working copy ({REPO_ROOT}):\n"
            f"      cp dbt/profiles.yml.example dbt/profiles.yml\n"
            f"      scripts/warehouse_tunnel.sh          # in another terminal, leave running\n"
            f"      python scripts/preflight_env.py\n\n"
            f"  See CLAUDE.md, \"Environments\".")

    return {"type": "postgres", "host": host, "port": str(port), "dbname": dbname,
            "user": user,
            "via": "ssh tunnel -> droplet warehouse" if host in LOOPBACK else "direct"}


def _probe(resolved: Dict[str, str], password: str) -> List[str]:
    """Ask the database what it is. A host string is a claim; this is the outcome.

    The reassigned-container-IP failure is why this is not optional: a tunnel can open
    successfully against nothing, or against whatever now holds the address, and the result
    is a connection that answers queries about the wrong data.
    """
    import psycopg2
    with psycopg2.connect(host=resolved["host"], port=int(resolved["port"]),
                          user=resolved["user"], password=password,
                          dbname=resolved["dbname"], connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select nspname from pg_namespace where nspname = any(%s)",
                           (list(WAREHOUSE_SCHEMAS),))
            found = sorted(row[0] for row in cursor.fetchall())
    if not found:
        raise PreflightError(
            f"connected to {resolved['host']}:{resolved['port']}/{resolved['dbname']} and it "
            f"is NOT THE WAREHOUSE.\n"
            f"  None of {', '.join(WAREHOUSE_SCHEMAS)} exist there. A database that answers\n"
            f"  is not the same as the right database -- if you are on a tunnel, the far end\n"
            f"  is probably pointing at a container address that has been reassigned.")
    return found


def check_env_keys() -> List[str]:
    """Name every missing variable at once, rather than failing on the first KeyError three
    layers down and making you discover them one run at a time."""
    return [key for key in REQUIRED_ENV if not os.getenv(key)]


# ------------------------------------------------------------------------------------------

def preflight(connect: bool = True) -> Dict[str, str]:
    where = working_copy()
    path, profile = resolve_profile()
    name, output = active_target(profile)

    if name in MANAGED_TARGETS:
        return {**where, "profile": str(path), "target": name,
                "note": "managed target -- host checks do not apply", "status": "skipped"}

    resolved = _check_host(name, output)
    missing = check_env_keys()
    if missing:
        raise PreflightError(
            "these variables are not set:\n    " + "\n    ".join(missing) +
            f"\n\n  Names and comments are in {REPO_ROOT / '.env.example'}; values are not,\n"
            f"  and never are. Copy it to .env and fill it in.")

    schemas: List[str] = []
    if connect and resolved.get("type") == "postgres":
        schemas = _probe(resolved, _render(output.get("password")))

    return {**where, "profile": str(path), "target": name, "status": "ok",
            "schemas": ", ".join(schemas) if schemas else "(not probed)", **resolved}


def banner(result: Dict[str, str]) -> str:
    order = ["path", "branch", "commit", "profile", "target", "via", "host", "port",
             "dbname", "user", "schemas", "note"]
    label = {"path": "working copy", "branch": "branch", "commit": "commit",
             "profile": "dbt profile", "target": "dbt target", "via": "reached",
             "host": "host", "port": "port", "dbname": "database", "user": "user",
             "schemas": "schemas seen", "note": "note"}
    lines = [f"  {label[k]:<13}: {result[k]}" for k in order if result.get(k)]
    return "cfdb preflight\n" + "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true", help="print only on failure")
    parser.add_argument("--no-connect", action="store_true",
                        help="skip the live probe; check configuration only")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    try:
        result = preflight(connect=not args.no_connect)
    except PreflightError as exc:
        where = working_copy()
        print(f"cfdb preflight FAILED\n  working copy : {where['path']}\n"
              f"  branch       : {where['branch']}\n\n{exc}", file=sys.stderr)
        return 1
    except Exception as exc:                                       # noqa: BLE001
        print(f"cfdb preflight FAILED\n  {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(banner(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
