"""The guard's own tests.

R-313. The point of scripts/preflight_env.py is that it fires on the developer profile and
NOT on the two managed ones, so these tests pin both halves. A guard that fails 665 times on
day one gets muted, and this project has done exactly that — the CI and Airflow cases below
are the ones that keep it from happening again.
"""
import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "preflight_env", REPO_ROOT / "scripts" / "preflight_env.py")
preflight_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preflight_env)

PreflightError = preflight_env.PreflightError


def _profile(tmp_path, outputs, target):
    path = tmp_path / "profiles.yml"
    path.write_text(yaml.safe_dump({"cfdb_profile": {"target": target, "outputs": outputs}}))
    return path


@pytest.fixture(autouse=True)
def _no_ambient_env(monkeypatch):
    """The developer's real .env must not decide the result of a test."""
    for key in ("DBT_TARGET", "DBT_PROFILES_DIR", "CFDB_WAREHOUSE_HOST",
                "CFDB_WAREHOUSE_PORT", "CFBD_API_KEY", "PG_HOST", "PG_PORT"):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------- it must fail ---

def test_missing_profile_names_the_file_and_the_working_copy(tmp_path, monkeypatch):
    """A FRESH WORKING COPY HAS NO PROFILE AT ALL — the case that was never diagnosed.

    One clone's root had no dbt/profiles.yml while its own worktree had one. Two directories
    of the same repository, in different states, neither visible to the other.
    """
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
    with pytest.raises(PreflightError) as exc:
        preflight_env.resolve_profile()
    message = str(exc.value)
    assert "NO DEVELOPER PROFILE IN THIS WORKING COPY" in message
    assert "profiles.yml.example" in message           # says what to do, not just what broke
    assert str(tmp_path) in message                    # says WHICH working copy


def test_the_dropped_database_is_refused(tmp_path, monkeypatch):
    """localhost:5432 is the stale template, verbatim. This is the bug, reproduced."""
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
    _profile(tmp_path, {"dev": {"type": "postgres", "host": "localhost", "port": 5432,
                                "user": "cfdb", "password": "cfdb", "dbname": "cfdb"}}, "dev")
    with pytest.raises(PreflightError) as exc:
        preflight_env.preflight(connect=False)
    assert "DROPPED ON 2026-09-05" in str(exc.value)


def test_empty_host_is_refused(tmp_path, monkeypatch):
    """An empty host is a unix socket on this machine — the same database, unnamed."""
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
    _profile(tmp_path, {"dev": {"type": "postgres", "host": "", "port": 5432,
                                "user": "cfdb", "password": "cfdb", "dbname": "cfdb"}}, "dev")
    with pytest.raises(PreflightError) as exc:
        preflight_env.preflight(connect=False)
    assert "EMPTY host" in str(exc.value)


def test_unset_variable_with_no_fallback_names_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
    _profile(tmp_path, {"warehouse": {"type": "postgres",
                                      "host": "{{ env_var('CFDB_WAREHOUSE_HOST') }}",
                                      "port": "{{ env_var('CFDB_WAREHOUSE_PORT') }}",
                                      "user": "cfdb", "password": "cfdb", "dbname": "cfdb"}},
             "warehouse")
    with pytest.raises(PreflightError) as exc:
        preflight_env.preflight(connect=False)
    assert "CFDB_WAREHOUSE_HOST is not set" in str(exc.value)


# ------------------------------------------------------- it must NOT fail CI/Airflow ---

@pytest.mark.parametrize("profile_dir, target", [
    ("dbt/profiles_ci", "ci"),
    ("dbt/profiles_airflow", "airflow"),
])
def test_the_committed_managed_profiles_pass(profile_dir, target, monkeypatch):
    """THE REAL FILES, NOT A FIXTURE. CI's profile resolves to localhost by design — the
    workflow's Postgres service container — and Airflow's to `postgres` on the compose
    network. Both are correct as written, and the guard exempts them by name."""
    monkeypatch.setenv("DBT_PROFILES_DIR", str(REPO_ROOT / profile_dir))
    result = preflight_env.preflight(connect=False)
    assert result["target"] == target
    assert result["status"] == "skipped"


def test_the_shipped_template_passes_once_its_variables_are_set(tmp_path, monkeypatch):
    """dbt/profiles.yml.example is what every working copy copies. If the guard rejected it,
    step 3 of the resync in CLAUDE.md would produce a profile that cannot pass step 4."""
    monkeypatch.setenv("DBT_PROFILES_DIR", str(REPO_ROOT / "dbt"))
    monkeypatch.setattr(preflight_env, "profiles_dir", lambda: tmp_path)
    (tmp_path / "profiles.yml").write_text(
        (REPO_ROOT / "dbt" / "profiles.yml.example").read_text())
    monkeypatch.setenv("CFDB_WAREHOUSE_HOST", "127.0.0.1")
    monkeypatch.setenv("CFDB_WAREHOUSE_PORT", "15433")
    monkeypatch.setenv("CFBD_API_KEY", "x")
    result = preflight_env.preflight(connect=False)
    assert result["status"] == "ok"
    # The supported path IS a loopback address, and the banner has to say so rather than
    # leaving "127.0.0.1" to be read as the database that was dropped.
    assert result["via"] == "ssh tunnel -> droplet warehouse"
    assert result["port"] == "15433"


def test_a_forwarded_loopback_port_is_not_the_dropped_database(tmp_path, monkeypatch):
    """The one judgement call in the guard, pinned: host alone cannot separate the good
    loopback from the bad one, so the PORT is what does it."""
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))
    monkeypatch.setenv("CFBD_API_KEY", "x")
    monkeypatch.setenv("CFDB_WAREHOUSE_HOST", "127.0.0.1")
    monkeypatch.setenv("CFDB_WAREHOUSE_PORT", "15433")
    _profile(tmp_path, {"warehouse": {"type": "postgres", "host": "127.0.0.1", "port": 15433,
                                      "user": "cfdb", "password": "cfdb", "dbname": "cfdb"}},
             "warehouse")
    assert preflight_env.preflight(connect=False)["status"] == "ok"


def test_env_keys_are_reported_together(monkeypatch):
    """Named all at once rather than one run at a time."""
    monkeypatch.setenv("CFDB_WAREHOUSE_HOST", "127.0.0.1")
    assert preflight_env.check_env_keys() == ["CFBD_API_KEY", "CFDB_WAREHOUSE_PORT"]
