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


def _render(target, which=None, selected=None, allow_local="0"):
    """Render the macro the way dbt would, with the context entries it relies on.

    ⚠️ A177: `which` and `selected` stand in for dbt's `flags.WHICH` and `selected_resources`.
    They default to ABSENT, which is what this harness supplied before the R-1327 guard existed
    and is what every test written before it still passes — the guard must be invisible to a
    caller that does not set them.
    """
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
    context = dict(
        target=target, execute=True, exceptions=_Exceptions(),
        log=lambda message, info=False: logged.append(message),
        env_var=lambda name, default=None: (
            allow_local if name == "CFDB_ALLOW_LOCAL_SERVING" else default),
    )
    if which is not None:
        context["flags"] = type("Flags", (), {"WHICH": which})()
    if selected is not None:
        context["selected_resources"] = selected

    out = template.render(**context)
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


# --------------------------------------------- A177: the local-build guard (R-1327) ---
#
# 🚨 THE GUARD EXISTS BECAUSE A LOCAL `dbt run` REACHED PRODUCTION. A170 measured the chain:
# dbt writes into the warehouse's own `serving` schema, and the scheduled publish copies that
# schema to the live serving database without asking whether the code is merged. Nothing
# reconciles it against the deployed manifest.
#
# ⚠️ THESE TESTS MATTER MORE THAN MOST, because this macro runs on EVERY production dbt
# invocation. A guard that fired there would stop the pipeline, so the first test below is the
# important one.

SERVING = ["model.cfdb_dbt.srv_team_week", "model.cfdb_dbt.srv_game_team"]
TUNNEL = _Target("warehouse", "127.0.0.1", 15433)


def test_production_is_never_refused_however_the_run_is_selected():
    """🚨 PRODUCTION RUNS `target: airflow` WITH `host: warehouse` — measured on the droplet's
    own scheduler, not assumed from this repo (whose committed profile is a different file).
    The host is what separates a laptop from the pipeline: a laptop reaches the same database
    over an SSH local-forward, so its host is loopback and production's never is.
    """
    for name in ("airflow", "ci"):
        sql, _ = _render(_Target(name, "warehouse", 5432), which="build", selected=SERVING)
        assert "select 1" in sql
    # And even under a non-managed name, a non-loopback host is not a laptop.
    sql, _ = _render(_Target("dev", "warehouse", 5432), which="build", selected=SERVING)
    assert "select 1" in sql


def test_a_local_build_of_a_serving_model_is_refused_and_says_why():
    with pytest.raises(_CompilerError) as exc:
        _render(TUNNEL, which="run", selected=SERVING)
    message = str(exc.value)
    assert "REFUSING to build 2 serving model(s)" in message
    assert "srv_game_team, srv_team_week" in message, "it must name them, sorted"
    assert "cfdb-main-R-1327" in message
    assert "CFDB_ALLOW_LOCAL_SERVING=1" in message, "the escape has to be discoverable"


def test_a_local_build_of_a_mart_is_not_refused():
    """⚠️ THE GUARD IS ABOUT WHAT THE PUBLISH COPIES, WHICH IS THE SERVING SCHEMA. Marts are
    not published directly, and a guard that blocked every local build would be routed around
    within a day."""
    sql, _ = _render(TUNNEL, which="run", selected=["model.cfdb_dbt.dim_team"])
    assert "select 1" in sql


def test_reading_commands_are_never_blocked():
    """`dbt test`, `compile`, `parse` and `docs` write nothing into serving. `compile` is the
    verification path the refusal message itself recommends, so blocking it would make the
    guard's own advice impossible to follow."""
    for which in ("test", "compile", "parse", "docs", "ls", "build-does-not-exist"):
        sql, _ = _render(TUNNEL, which=which, selected=SERVING)
        assert "select 1" in sql, which


def test_the_named_escape_actually_works():
    sql, _ = _render(TUNNEL, which="run", selected=SERVING, allow_local="1")
    assert "select 1" in sql


def test_the_guard_is_silent_when_dbt_supplies_no_context():
    """⚠️ `flags` and `selected_resources` are dbt's, not Jinja's. Reaching for either unguarded
    raises `'flags' is undefined` and takes the whole on-run-start with it — which is how the
    tunnel test above caught this guard's first draft. Absent context means "not a build"."""
    sql, _ = _render(TUNNEL)
    assert "select 1" in sql
