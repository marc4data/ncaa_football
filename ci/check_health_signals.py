"""Assert the CI fixture makes every System Overview signal escalate.

srv_system_health is the page that answers "is anything wrong". It carries five signal
types, each with its own severity ladder, and until now exactly one of those ladders had
ever been observed climbing: the deployment signal, because its fixture row was written
stale on purpose. The other four were assumed to work.

An alarm nobody has seen fire is an assumption, not a control. The failure it guards
against is silent by construction — a severity branch that never evaluates true looks
identical to a system that is healthy, and the difference only surfaces on the day
something actually breaks, which for this project is a Saturday in October.

Three checks, in order of how badly each would hurt:

  1. Every signal type the model can emit produces at least one row. A signal that emits
     nothing does not appear as a problem on the page — it appears as nothing at all. This
     is the check that catches an empty fct_deploy_status or a mart_as_of with no 'ops'
     row, either of which would quietly delete rows from a status board.

  2. Every signal type produces at least one NON-ok row, so its escalating branch is
     evaluated on every build. Only one severity per subject is observable at a time —
     these signals report current state, not history — so this asserts that the branch CI
     exercises is the alarm rather than the all-clear.

  3. Every severity is a value the page knows how to sort and colour. A new branch emitting
     'critical' or NULL would render as an unstyled row rather than an error.

The expected signal list is READ OUT OF THE MODEL, never hardcoded here. A sixth signal
type added without a fixture that escalates it fails this check on the commit that adds it,
which is the only time the fixture is cheap to write.
"""
import os
import re
import sys
from pathlib import Path

MODEL = Path("dbt/models/serving/srv_system_health.sql")

# The severities the page's sort order and colour map are built around.
KNOWN_SEVERITIES = {"ok", "warn", "error", "unknown"}

# 'unknown' means "no threshold published", not "a threshold was crossed". Counting it as
# escalation would let the quota signal satisfy check 2 without either alarm branch ever
# running — which is exactly the gap this file was written to close.
ESCALATING = {"warn", "error"}


def declared_signal_types() -> set:
    """Signal types the model can emit, parsed from its own select list."""
    if not MODEL.exists():
        print(f"ERROR: {MODEL} not found")
        sys.exit(1)
    sql = MODEL.read_text(encoding="utf-8")
    # Matches   'freshness'   as signal_type
    return set(re.findall(r"'([a-z_]+)'\s+as\s+signal_type", sql))


def observed() -> list:
    import psycopg2

    connection = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "cfdb"),
        user=os.getenv("PG_USER", "cfdb"),
        password=os.getenv("PG_PASSWORD", "cfdb"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select signal_type, severity, count(*)
                from serving.srv_system_health
                group by 1, 2
                order by 1, 2
            """)
            return cursor.fetchall()
    finally:
        connection.close()


def main() -> int:
    declared = declared_signal_types()
    if not declared:
        print(f"ERROR: no signal types found in {MODEL} — has the select list changed shape?")
        return 1

    rows = observed()
    if not rows:
        # The cross join to mart_as_of can empty the entire view if the 'ops' domain is
        # missing. That is a total page blackout, so it gets its own message.
        print("ERROR: serving.srv_system_health returned no rows at all.")
        print("       Every signal is unioned then cross joined to mart_as_of; a missing")
        print("       'ops' domain there empties the whole view rather than one signal.")
        return 1

    by_type = {}
    for signal_type, severity, count in rows:
        by_type.setdefault(signal_type, {})[severity] = count

    failures = []

    missing = declared - set(by_type)
    if missing:
        failures.append(
            f"signal type(s) declared in the model but emitting no rows: "
            f"{', '.join(sorted(missing))}")

    undeclared = set(by_type) - declared
    if undeclared:
        failures.append(
            f"signal type(s) in the data that the model does not declare — the parse above "
            f"is out of date: {', '.join(sorted(undeclared))}")

    for signal_type in sorted(declared & set(by_type)):
        severities = set(by_type[signal_type])
        if not severities & ESCALATING:
            failures.append(
                f"'{signal_type}' never escalates in the fixture (only {sorted(severities)}) "
                f"— add a fixture row that trips its warn or error threshold")

    unknown_severities = {s for counts in by_type.values() for s in counts} - KNOWN_SEVERITIES
    if unknown_severities:
        failures.append(
            f"severity value(s) the page cannot sort or colour: "
            f"{', '.join(sorted(str(s) for s in unknown_severities))}")

    print(f"{'signal type':16s} {'severities observed':40s}")
    for signal_type in sorted(by_type):
        rendered = ", ".join(f"{sev}={n}" for sev, n in sorted(by_type[signal_type].items()))
        mark = "  " if set(by_type[signal_type]) & ESCALATING else "!!"
        print(f"{mark} {signal_type:14s} {rendered}")

    if failures:
        print()
        for failure in failures:
            print(f"::error::{failure}")
        return 1

    print(f"\nAll {len(declared)} health signal(s) present, and every one escalates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
