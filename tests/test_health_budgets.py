"""A162 — the heartbeat budgets live in two places, so a test holds them together.

🚨 THE DUPLICATION IS UNAVOIDABLE AND THEREFORE GUARDED. `ci/check_heartbeats.py` runs on
GitHub Actions, in Python, from outside the droplet — that placement is the whole design, so
that a monitor does not share fate with the thing it monitors. `srv_system_health` runs in the
warehouse, in SQL, so a stopped publish is visible on the page a reader already opens. **There
is no shared home for a number both of them need.**

⚠️ §4.2.1's question is "how many consumers can this number have", and the answer here is two,
in two languages, on two machines. **A number with two homes needs a guard, not a comment** —
if one budget moves and the other does not, the page and the dead-man's switch disagree about
whether the pipeline is healthy, and nothing says so.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ci"))

# ⚠️ THE BUDGETS LIVE IN THE MART, NOT IN SERVING. `ci/check_layering.py` rule 3 sends the
# grain change to `fct_pipeline_heartbeat`; this guard follows the numbers, not the page.
MODEL = ROOT / "dbt/models/marts/fct_pipeline_heartbeat.sql"


def _budgets_from_sql():
    """The `case heartbeat_name when 'x' then N * 3600` arm, as {name: seconds}."""
    body = MODEL.read_text()
    block = re.search(r"case heartbeat_name(.*?)end\s+as budget_seconds", body, re.S)
    assert block, "the budget CASE has moved or been renamed — this guard cannot see it"
    out = {}
    for name, expr in re.findall(r"when '([a-z_]+)' then ([0-9 *]+)", block.group(1)):
        out[name] = eval(expr, {"__builtins__": {}})      # digits and * only, from our own file
    return out


def _budgets_from_checker():
    import check_heartbeats
    return {name: seconds for name, (_cadence, seconds)
            in check_heartbeats.CADENCES.items()}


def test_the_health_model_budgets_match_the_dead_mans_switch():
    """Both sides, by name and by number. Neither may move alone."""
    sql, py = _budgets_from_sql(), _budgets_from_checker()
    assert sql == py, (
        f"the heartbeat budgets disagree.\n"
        f"  srv_system_health.sql : {sorted(sql.items())}\n"
        f"  ci/check_heartbeats.py: {sorted(py.items())}\n"
        f"If a cadence changed, move BOTH — otherwise the page and the dead-man's switch "
        f"disagree about whether the pipeline is healthy and nothing says so.")


def test_every_budgeted_cadence_is_one_the_pipeline_actually_beats():
    """🚨 A BUDGET FOR A CADENCE NOTHING WRITES IS A ROW THAT CAN NEVER GO RED (R-760).

    The names are asserted against the DAGs that own the `beat` task, not against a list
    somebody retyped — so retiring a DAG without retiring its budget fails here.
    """
    dag_text = "\n".join(p.read_text() for p in (ROOT / "dags").glob("*.py"))
    for name in _budgets_from_checker():
        assert name in dag_text, (
            f"{name!r} is budgeted in both places and no DAG writes it — either the cadence "
            f"was retired and its budget outlived it, or the heartbeat name changed")
