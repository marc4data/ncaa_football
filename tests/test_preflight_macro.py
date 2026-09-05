"""What dbt/macros/preflight_target.sql actually emits, and when it raises.

`dbt parse` catches a Jinja SYNTAX error in the macro but never executes it — on-run-start
runs only on a real `dbt run`/`build`, against a real connection. So the branch that matters
(CI and Airflow must not be refused) would otherwise be unverified until it broke CI.

This renders the macro body with dbt's own Jinja dialect and a stubbed `target`, which pins
two things: the SQL it hands back to dbt is exactly `select 1`, and each target name lands in
the branch it is supposed to.
"""
import re
from pathlib import Path

import pytest
from jinja2 import Environment

MACRO = Path(__file__).resolve().parents[1] / "dbt" / "macros" / "preflight_target.sql"


class _CompilerError(RuntimeError):
    pass


class _Target:
    def __init__(self, name, host, port, type_="postgres"):
        self.name, self.host, self.port, self.type = name, host, port, type_
        self.dbname, self.schema, self.profile_name = "cfdb", "public", "cfdb_profile"


def _render(target):
    """Render the macro the way dbt would, with the context entries it relies on."""
    body = MACRO.read_text()
    # Strip the {# ... #} doc block; Jinja handles it, but keeping the macro alone makes the
    # failure message point at the macro rather than at its comment.
    body = re.sub(r"\{#.*?#\}", "", body, flags=re.DOTALL)

    logged = []

    class _Exceptions:
        @staticmethod
        def raise_compiler_error(message):
            raise _CompilerError(message)

    # dbt enables the `do` extension; plain Jinja2 does not, and the macro uses {% do %}.
    env = Environment(extensions=["jinja2.ext.do"])
    template = env.from_string(body + "\n{{ preflight_target() }}")
    out = template.render(
        target=target, execute=True, exceptions=_Exceptions(),
        log=lambda message, info=False: logged.append(message),
    )
    return out.strip(), logged


# ------------------------------------------------------------------ it must refuse ---

def test_the_dropped_database_raises():
    with pytest.raises(_CompilerError) as exc:
        _render(_Target("dev", "localhost", 5432))
    assert "DROPPED ON 2026-09-05" in str(exc.value)


def test_an_empty_host_raises():
    with pytest.raises(_CompilerError) as exc:
        _render(_Target("dev", "", 5432))
    assert "EMPTY host" in str(exc.value)


# ----------------------------------------------- it must not refuse CI or Airflow ---

@pytest.mark.parametrize("target", [
    _Target("ci", "localhost", 5432),          # the workflow's Postgres service container
    _Target("airflow", "postgres", 5432),      # the compose network
])
def test_managed_targets_pass(target):
    """THE ONE THAT KEEPS THE GUARD ALIVE. If this ever fails, CI goes red on every PR and
    the guard gets deleted rather than fixed."""
    sql, logged = _render(target)
    assert sql == "select 1"
    assert len(logged) == 1


def test_the_tunnel_passes_and_is_named_in_the_log():
    sql, logged = _render(_Target("warehouse", "127.0.0.1", 15433))
    assert sql == "select 1"
    assert "ssh tunnel" in logged[0]


def test_it_hands_dbt_valid_sql_and_nothing_else():
    """The hook's return value is executed as SQL. Anything the macro leaks into it — a
    stray banner line, a rendered comment — becomes a syntax error on every dbt run."""
    sql, _ = _render(_Target("warehouse", "10.0.0.5", 5432))
    assert sql == "select 1"
