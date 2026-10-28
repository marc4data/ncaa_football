"""🚨 A290 (cfdb-main-R-5012). THE DEPLOY SIGNAL PUBLISHED A GREEN `ok` FOR 67 DAYS.

📊 Measured on the warehouse 2026-10-28: `marts.fct_deploy_status where recency_rank = 1` read
`severity ok · "Deploy tree matches main at 9bb72cc" · observed_at 2026-08-22 07:36:26Z` —
naming a commit 60+ commits behind `main`. `srv_system_health`'s `deployment` signal published
that `severity` verbatim, so the status board showed a green deploy-drift light all autumn.

🚨 AND THE CAUSE WAS THE ABSENCE OF A WRITER: `git log -S "src.deploy_status"` across every ref
finds no committed caller, ever. The module landed 2026-08-19, was revised 2026-09-06, and the
one observation between them was a hand run.

⚠️ WHY THIS TEST EXECUTES SQL RATHER THAN READING IT. `srv_system_health` is a SERVING model and
R-1327 refuses a local serving build, so the usual route — build it and select from it — is
closed by design. Asserting on the compiled text instead would pin the STRING and not the
BEHAVIOUR, which is how a guard comes to pass on logic that does not work. So this renders the
real macro through `dbt compile --inline` and runs it over synthetic observations.

⚠️ IT SKIPS WITHOUT A WAREHOUSE, the same way `test_disk_source` does: the `flake8 + pytest` CI
job has no database, and a test that cannot reach one must say so rather than fail.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DBT = ROOT / "dbt"
BUDGET_DAYS = 14          # dbt_project.yml: deploy_status_stale_days

# (label, severity, the observation's age in days, the severity that must be published)
CASES = [
    ("a fresh ok is still ok",                 "ok",     0,   "ok"),
    ("an ok just inside the budget survives",  "ok",     13,  "ok"),
    # 🚨 THE ROUND'S WHOLE POINT. 67 days is what production was actually publishing.
    ("the 67-day-old ok must NOT read ok",     "ok",     67,  "unknown"),
    ("one day past the budget already goes",   "ok",     15,  "unknown"),
    # A real verdict is kept while it is fresh — the bound degrades, it does not blanket.
    ("a fresh error is preserved",             "error",  1,   "error"),
    ("a fresh warn is preserved",              "warn",   2,   "warn"),
    # An old error is no more evidence than an old ok.
    ("a stale error is also not evidence",     "error",  40,  "unknown"),
]


def _warehouse_available() -> bool:
    import socket
    host = os.environ.get("CFDB_WAREHOUSE_HOST", "127.0.0.1")
    port = int(os.environ.get("CFDB_WAREHOUSE_PORT", "15433"))
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def _render(expression: str) -> str:
    """Render one macro call through dbt, so the SQL under test is the SHIPPED SQL."""
    out = subprocess.run(
        ["dbt", "compile", "--quiet", "--inline", expression],
        cwd=DBT, capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip(f"dbt compile --inline unavailable here: {out.stderr[-300:]}")
    return out.stdout


@pytest.fixture(scope="module")
def run_sql():
    if not _warehouse_available():
        pytest.skip("no warehouse reachable from here — open scripts/warehouse_tunnel.sh")
    import psycopg2
    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
               if "=" in line and not line.startswith("#"))
    connection = psycopg2.connect(
        host=os.environ.get("CFDB_WAREHOUSE_HOST", "127.0.0.1"),
        port=int(os.environ.get("CFDB_WAREHOUSE_PORT", "15433")),
        dbname=env.get("PG_DB", "cfdb").strip(), user=env.get("PG_USER", "cfdb").strip(),
        password=env["PG_PASSWORD"].strip())

    def run(sql):
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    yield run
    connection.close()


@pytest.mark.parametrize("label,severity,age_days,expected", CASES)
def test_a_stale_observation_cannot_publish_its_old_verdict(run_sql, label, severity,
                                                            age_days, expected):
    rendered = _render(
        "select {{ deploy_observation_severity('sev', 'obs') }} as published "
        "from (select %(sev)s::text as sev, "
        "      now() - interval %(age)s as obs) t")
    # the inline model is compiled with the params still as placeholders; bind them now
    rows = run_sql_with(run_sql, rendered, {"sev": severity, "age": f"{age_days} days"})
    assert rows and rows[0][0] == expected, (
        f"{label}: a {age_days}-day-old {severity!r} published {rows and rows[0][0]!r}, "
        f"expected {expected!r}")


def run_sql_with(run, sql, params):
    """psycopg2 interpolation, kept out of the test body so the assertion reads cleanly."""
    import psycopg2.extensions as ext           # noqa: F401
    rendered = sql.replace("%(sev)s", f"'{params['sev']}'") \
                  .replace("%(age)s", f"'{params['age']}'")
    return run(rendered)


def test_the_detail_says_how_old_the_observation_is(run_sql):
    """⚠️ A severity of `unknown` with no explanation sends the reader to the warehouse. The
    detail has to carry the age AND what the stale verdict used to say."""
    rendered = _render(
        "select {{ deploy_observation_detail('det', 'obs') }} as detail "
        "from (select 'Deploy tree matches main at 9bb72cc'::text as det, "
        "      now() - interval '67 days' as obs) t")
    detail = run_sql(rendered)[0][0]
    assert "STALE" in detail, detail
    assert "67" in detail, detail
    assert "9bb72cc" in detail, f"the superseded verdict is lost: {detail}"
    assert str(BUDGET_DAYS) in detail, detail


def test_a_null_observation_is_unknown_and_says_it_has_never_been_recorded(run_sql):
    sev = run_sql(_render(
        "select {{ deploy_observation_severity('sev', 'obs') }} as s "
        "from (select 'ok'::text as sev, null::timestamptz as obs) t"))[0][0]
    assert sev == "unknown", sev
    det = run_sql(_render(
        "select {{ deploy_observation_detail('det', 'obs') }} as d "
        "from (select 'anything'::text as det, null::timestamptz as obs) t"))[0][0]
    assert "has ever been recorded" in det, det


def test_the_threshold_has_one_home():
    """R-574. The severity and the detail must agree about what stale means, so both read the
    same var and neither hardcodes a number."""
    macro = (DBT / "macros" / "deploy_observation.sql").read_text()
    assert macro.count("deploy_status_stale_days") >= 2, (
        "the budget is not read from the var in both the severity and the detail")
    assert not re.search(r"interval\s+'1[0-9]+\s+days'", macro), (
        "a day count is hardcoded in the macro instead of coming from the var")
    model = (DBT / "models" / "serving" / "srv_system_health.sql").read_text()
    assert "deploy_observation_severity" in model and "deploy_observation_detail" in model
    assert "recency_rank = 1" in model, "the signal no longer reads the newest observation"
