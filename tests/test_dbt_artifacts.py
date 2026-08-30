"""Where dbt writes its artifacts, and where we look for them.

These have to agree. dbt drops run_results.json under the project's `target/`, inside the
code checkout — fine on a laptop, wrong on a server where the checkout is root-owned and the
container runs as uid 50000. Moving target/ out of the checkout is the fix; a reader that
still looks in the old place would capture nothing and say so to nobody.
"""


# --- dbt artifacts live where dbt was told to put them ------------------------------------

def test_the_artifact_path_follows_dbt_target_path(monkeypatch):
    """dbt writes target/ inside the code checkout by default. On the droplet the checkout is
    root-owned and the container is uid 50000, so dbt cannot write there — it dies during
    logging setup, before it can print why, and exits 2 with no output at all.

    Moving target/ out of the checkout fixes that, but only if the reader follows. A capture
    that still looks in dbt/target would silently record nothing.
    """
    import importlib
    monkeypatch.setenv("DBT_TARGET_PATH", "/var/lib/cfdb/dbt-target")
    from src import dbt_artifacts
    importlib.reload(dbt_artifacts)
    assert str(dbt_artifacts.DEFAULT_ARTIFACT) == "/var/lib/cfdb/dbt-target/run_results.json"


def test_the_default_is_unchanged_when_dbt_target_path_is_unset(monkeypatch):
    """The laptop sets nothing and must keep working exactly as before."""
    import importlib
    monkeypatch.delenv("DBT_TARGET_PATH", raising=False)
    from src import dbt_artifacts
    importlib.reload(dbt_artifacts)
    assert str(dbt_artifacts.DEFAULT_ARTIFACT) == "dbt/target/run_results.json"
