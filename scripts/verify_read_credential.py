#!/usr/bin/env python
"""Prove the laptop's `cfdb_read` credential is usable AND read-only (R-445).

    scripts/serving_tunnel.sh            # another terminal, leave it running
    python scripts/verify_read_credential.py

WHY THIS EXISTS RATHER THAN A SENTENCE IN A README.

README.md said the read role "has SELECT and nothing else — verified against
INSERT/DELETE/CREATE/DROP at creation". Verified once, at creation, by someone who is no
longer in the room is an assertion, not a limit: the role can be recreated, re-granted, or
granted into a group, and nothing would notice. Marc's ruling of 2026-09-08 puts this
credential on laptops, which widens where it is held — so what it can do has to be
MEASURED, from the machine that holds it, on demand.

It prints a FINGERPRINT and never the secret. Every check reports what actually happened,
and a check that cannot run says so rather than counting as a pass — a write that fails
because the table does not exist has proved nothing about permissions.

Exit 0 only if the credential reads serving and is refused everywhere else.
"""
import hashlib
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]

# Schemas the credential must NOT be able to read. serving is the only one it may.
FORBIDDEN_SCHEMAS = ("raw", "staging", "marts", "public")


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _fingerprint(secret: str) -> str:
    """The first eight hex of sha256. Enough to compare two machines, useless to an
    attacker, and the form B066 established when it found local and droplet differing."""
    return hashlib.sha256(secret.encode()).hexdigest()[:8] + "…"


def main() -> int:
    _load_env()
    user = os.getenv("CFDB_READ_USER", "cfdb_read")
    password = os.getenv("CFDB_READ_PASSWORD", "")
    host = os.getenv("SERVING_PG_HOST", os.getenv("CFDB_PUBLISHED_HOST", "127.0.0.1"))
    port = os.getenv("SERVING_PG_PORT", os.getenv("CFDB_PUBLISHED_PORT", "15434"))
    database = os.getenv("SERVING_PG_DB", "cfdb")

    if not password:
        print("CFDB_READ_PASSWORD is empty. See README.md, 'The laptop read credential'.")
        return 2

    print(f"role        : {user}")
    print(f"target      : {host}:{port}/{database}")
    print(f"fingerprint : {_fingerprint(password)}   (never the secret itself)")
    print()

    try:
        conn = psycopg2.connect(host=host, port=port, dbname=database, user=user,
                                password=password, connect_timeout=15)
    except psycopg2.OperationalError as exc:
        first = str(exc).strip().splitlines()[0]
        print(f"CONNECT FAILED: {first}")
        print()
        if "password authentication failed" in first:
            print("The credential is STALE or wrong. This is the B066 finding: the laptop")
            print("copy and the droplet's differ. It is NOT a tunnel problem — the refusal")
            print("came from the serving Postgres, so the forward is working.")
        else:
            print("Nothing answered. Is scripts/serving_tunnel.sh running?")
        return 1

    conn.autocommit = True
    failures = []

    with conn.cursor() as cur:
        # ---- 1. IT CAN READ SERVING, which is the whole point of having it -------------
        cur.execute("select count(*) from information_schema.tables "
                    "where table_schema = 'serving'")
        n_tables = cur.fetchone()[0]
        print(f"serving objects visible : {n_tables}")
        if n_tables == 0:
            failures.append("cannot see any serving object — SELECT was not granted")

        # ---- 2. THE GRANTS, READ OUT OF THE CATALOGUE RATHER THAN ASSERTED ------------
        cur.execute(
            "select distinct privilege_type from information_schema.role_table_grants "
            "where grantee = %s and table_schema = 'serving' order by 1", (user,))
        serving_privs = [r[0] for r in cur.fetchall()]
        print(f"privileges on serving   : {', '.join(serving_privs) or '(none)'}")
        beyond = sorted(set(serving_privs) - {"SELECT"})
        if beyond:
            failures.append(f"holds more than SELECT on serving: {beyond}")

        cur.execute(
            "select table_schema, array_agg(distinct privilege_type order by privilege_type) "
            "from information_schema.role_table_grants where grantee = %s "
            "and table_schema <> 'serving' group by 1 order by 1", (user,))
        other = cur.fetchall()
        print(f"privileges elsewhere    : "
              f"{', '.join(f'{s}={p}' for s, p in other) if other else '(none)'}")
        if other:
            failures.append(f"holds grants outside serving: {[s for s, _ in other]}")

        # ---- 3. SCHEMA-LEVEL REACH ----------------------------------------------------
        # 🚨 R-566. WHICH SCHEMAS EXIST IS ASKED FIRST, AND THE REASON IS A CRASH.
        #
        # `has_schema_privilege` RAISES InvalidSchemaName on a schema that does not exist, and
        # the serving instance has no `raw` — only the warehouse does. So this loop died on its
        # first forbidden schema with a traceback, every run, and NEVER REACHED the write
        # probes below it. R-566 recorded this as "exits non-zero on success"; measured, it is
        # worse than that — the verification was not completing at all, and the two checks it
        # never got to are the ones that prove the credential cannot write.
        #
        # ⚠️ AN ABSENT SCHEMA IS A PASS, AND IT IS THE STRONGEST FORM OF ONE: a schema that
        # does not exist on this instance cannot be read from it. Reported as `absent` rather
        # than silently skipped, so the line still says what was and was not measured.
        cur.execute("select schema_name from information_schema.schemata")
        present = {row[0] for row in cur.fetchall()}
        for schema in ("serving",) + FORBIDDEN_SCHEMAS:
            if schema not in present:
                print(f"  schema {schema:<9} absent on this instance  <- cannot be read")
                continue
            cur.execute("select has_schema_privilege(%s, %s, 'USAGE')", (user, schema))
            usable = cur.fetchone()[0]
            cur.execute("select has_schema_privilege(%s, %s, 'CREATE')", (user, schema))
            creatable = cur.fetchone()[0]
            print(f"  schema {schema:<9} USAGE={str(usable):<5} CREATE={creatable}")
            if schema != "serving" and usable:
                failures.append(f"can USAGE schema {schema}")
            if creatable:
                failures.append(f"can CREATE in schema {schema}")

        # ---- 4. IT IS NOT A SUPERUSER AND INHERITS NOTHING USEFUL --------------------
        cur.execute("select rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                    "from pg_roles where rolname = %s", (user,))
        row = cur.fetchone()
        if row:
            su, cdb, crole, bypass = row
            print(f"role attrs  : superuser={su} createdb={cdb} createrole={crole} "
                  f"bypassrls={bypass}")
            for label, held in (("superuser", su), ("createdb", cdb),
                                ("createrole", crole), ("bypassrls", bypass)):
                if held:
                    failures.append(f"role attribute {label} is set")

        cur.execute("select r.rolname from pg_auth_members m "
                    "join pg_roles r on r.oid = m.roleid "
                    "join pg_roles u on u.oid = m.member where u.rolname = %s", (user,))
        member_of = [r[0] for r in cur.fetchall()]
        print(f"member of   : {', '.join(member_of) or '(nothing)'}")
        if member_of:
            failures.append(f"is a member of {member_of} — inherited rights are not audited")

        # ---- 5. THE WRITES ARE ACTUALLY ATTEMPTED, NOT ASSUMED ------------------------
        # ⚠️ Against a REAL serving table. A write refused because the table does not exist
        # proves nothing about permissions, so the target is resolved first and the check
        # is reported as INCONCLUSIVE rather than passing if there is nothing to write to.
        cur.execute("select table_name from information_schema.tables "
                    "where table_schema = 'serving' and table_type = 'BASE TABLE' "
                    "order by table_name limit 1")
        target = cur.fetchone()
        print()
        if not target:
            print("write checks : INCONCLUSIVE — no base table in serving to attempt against")
            failures.append("could not attempt a write against any real serving table")
        else:
            table = target[0]
            attempts = {
                "INSERT": f'insert into serving."{table}" default values',
                "UPDATE": f'update serving."{table}" set "{table}" = null where false',
                "DELETE": f'delete from serving."{table}" where false',
                "CREATE": "create table serving._cfdb_read_probe (x int)",
                "DROP":   f'drop table serving."{table}"',
            }
            for label, sql in attempts.items():
                try:
                    cur.execute(sql)
                except psycopg2.errors.InsufficientPrivilege:
                    print(f"  {label:<7} REFUSED (insufficient privilege)  <- correct")
                except psycopg2.Error as exc:
                    # Refused for some OTHER reason. Not a permission proof; say so.
                    name = type(exc).__name__
                    print(f"  {label:<7} blocked by {name}, NOT by privilege  <- inconclusive")
                    failures.append(f"{label} was refused by {name}, not by privilege")
                else:
                    print(f"  {label:<7} SUCCEEDED  <- THIS IS A WRITE CREDENTIAL")
                    failures.append(f"{label} succeeded against serving.{table}")

        # ---- 6. THE ACCEPTANCE CRITERION: ONE ROW, FROM A LAPTOP ---------------------
        print()
        cur.execute("select count(*) from serving.srv_game")
        print(f"select count(*) from serving.srv_game  ->  {cur.fetchone()[0]:,}")
        cur.execute("select game_id, season, week, home_team_display, away_team_display "
                    "from serving.srv_game order by game_id limit 1")
        print(f"one row from serving.srv_game          ->  {cur.fetchone()}")

    conn.close()
    print()
    if failures:
        print("NOT A READ-ONLY CREDENTIAL — " + str(len(failures)) + " problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — reads serving, refused everywhere else. Limits measured, not assumed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
