"""Execute every query the site issues, against the fixture-built serving layer.

`test_built_pages_pass_the_query_contract` proves each query is legally SHAPED — one
serving relation, no join, an explicit limit. It cannot prove the columns exist, and that
gap shipped a broken page: Scores asked srv_game for eight columns it did not have
(start_date_et, both team slugs, both display names, both poll ranks, venue_display) and
had been raising on every single load since it was written.

Nobody noticed, and the reason is worth stating. `states.section` catches the exception and
renders the Error state — plain language, the view name, no traceback, exactly as designed.
So the page looked like a handled failure rather than a defect. A graceful degradation the
author never watches fire is indistinguishable from a working page, which is the same
lesson the deployment alarm taught one round earlier.

The check is deliberately about EXECUTION, not results. A fixture returning zero rows is
fine; a fixture that cannot answer the question at all is not. That means this catches
renamed and dropped columns, which is the failure mode that actually happens — serving
views are rewritten far more often than pages are.

Run after `dbt build` against the fixture database:
    python ci/check_page_queries.py
"""
import os
import re
import sys
from pathlib import Path

SITE = Path("site")

# One SQL string literal, triple-quoted, starting with SELECT. Every query in the site is
# written this way; anything assembled from fragments would be invisible here, which is a
# reason not to assemble queries from fragments.
SQL = re.compile(r'"""\s*(select\b.*?)"""', re.DOTALL | re.IGNORECASE)

# f-string holes that appear inside query literals, and what to put there so the SQL parses.
# Kept short on purpose: a query needing more interpolation than this is a query that should
# not be interpolated.
#
# These are the holes whose value is a bare identifier chosen at runtime — a sort direction,
# say. Holes filled from a module-level constant are resolved from the module itself, below,
# because substituting a placeholder for a COLUMN LIST would validate nothing: the check
# exists to prove the columns are real, and `select *` proves only that the table is.
SUBSTITUTIONS = {
    "{rank_field}": "rank_desc",
    # R-165's conference list runs the same query once per side of the fixture, so the two
    # halves differ only by this prefix. Resolving it to one side means the check still
    # EXECUTES the query rather than waving it through — which is the whole point of this
    # script, and why a substitution is the right answer here rather than an exemption.
    "{side}": "home",
    # The workbook's row cap is a named constant interpolated into every sheet query, because
    # the contract's LIMIT check matches `limit <digits>` and a bind parameter would fail it.
    # Any integer executes the same query; the value is not what is under test here.
    "{ROW_CAP}": "5000",
}

# A value per bind parameter, so the query executes. These are not assertions about the
# fixture's contents — the point is that the SQL runs, not that it matches anything.
BINDINGS = {
    "season": 2024, "week": 1, "season_type": "regular", "game_id": 9001,
    "minimum": 0.0, "market": "spread", "stat_name": "firstDowns",
    "undocumented": False, "search": "", "pattern": "%",
    "division": "fbs", "poll": "AP Top 25",
}
# Anything not named above binds NULL, which every one of these queries tolerates because
# the optional filters are all written `(:x is null or col = :x)`.
DEFAULT_BINDING = None


def module_constants(source: str) -> dict:
    """Module-level `NAME = "..."` string constants, for resolving f-string holes.

    A page that shares one column list between two queries writes it as a constant and
    interpolates it, which is correct — the alternative is two copies that drift. Reading
    the constant back means the check still sees the real column names rather than a
    wildcard, which is the entire point of running these against a database.

    Parsed rather than imported: importing a page module pulls in streamlit and opens a
    database connection at import time, and this runs before either is wanted.
    """
    import ast
    constants = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                constants[target.id] = node.value.value
    return constants


def statements():
    # R-182. `views/`, NOT `pages/` — AND THIS CHECK WAS GREEN WHILE SCANNING NEITHER.
    #
    # The directory was renamed from `pages/` to `views/` because Streamlit auto-discovers a
    # folder called `pages/` and builds a competing multipage app from it. The Dockerfile was
    # updated, the deploy instructions eventually were, and this glob was not. `Path.glob` on a
    # directory that does not exist yields nothing and raises nothing, so the job kept passing
    # while checking 10 statements out of `lib/` and NONE of the eighteen page modules.
    #
    # It was found by negative-testing the pytest wrapper around it: a deliberately broken
    # column was reintroduced into schedule.py and the checker still passed. A verification
    # that cannot fail is not a verification — R-157, and the sharpest instance of it yet
    # because this one had a whole CI job named after it.
    #
    # ASSERTED, NOT ASSUMED, below: an empty scan is now an error rather than a pass.
    files = sorted(SITE.joinpath("views").glob("*.py")) + \
        sorted(SITE.joinpath("lib").glob("*.py"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        constants = module_constants(source)
        for raw in SQL.findall(source):
            sql = " ".join(raw.split())
            for name, value in constants.items():
                sql = sql.replace("{" + name + "}", " ".join(value.split()))
            for hole, value in SUBSTITUTIONS.items():
                sql = sql.replace(hole, value)
            if "{" in sql:
                # An uncovered interpolation would become a syntax error and read as a
                # broken query rather than an unsupported one. Say which it is.
                yield path, sql, f"uninterpolated placeholder in {path.name}"
                continue
            yield path, sql, None


def main() -> int:
    import psycopg2

    # A scan that finds nothing is the failure this script spent months not reporting.
    scanned = list(statements())
    if len(scanned) < 20:
        print(f"::error::check_page_queries scanned only {len(scanned)} statements — the "
              f"source globs are wrong, not the queries", file=sys.stderr)
        return 1

    connection = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "cfdb"),
        user=os.getenv("PG_USER", "cfdb"),
        password=os.getenv("PG_PASSWORD", "cfdb"),
    )
    # Autocommit, because a failed statement aborts the transaction and would take the
    # search_path with it — every query after the first failure would then fail for the
    # wrong reason and the report would name the wrong page.
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute("set search_path to serving, public")

    failures, checked = [], 0
    for path, sql, problem in statements():
        checked += 1
        if problem:
            failures.append((path.name, sql[:80], problem))
            continue
        names = set(re.findall(r":(\w+)", sql))
        runnable = re.sub(r":(\w+)", r"%(\1)s", sql)
        binding = {name: BINDINGS.get(name, DEFAULT_BINDING) for name in names}
        try:
            cursor.execute(runnable, binding)
            cursor.fetchall()
        except Exception as exc:                                   # noqa: BLE001
            failures.append((path.name, sql[:80], str(exc).splitlines()[0]))

    connection.close()

    if not checked:
        print("::error::found no page queries at all — has the literal style changed?")
        return 1

    print(f"Executed {checked} page query/queries against the serving layer.")
    if failures:
        print()
        for name, sql, err in failures:
            print(f"::error::{name}: {err}")
            print(f"    {sql}")
        return 1
    print("Every query the site issues resolves against the views it reads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
