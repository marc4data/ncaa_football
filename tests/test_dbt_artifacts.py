"""Where dbt writes its artifacts, and where we look for them.

These have to agree. dbt drops run_results.json under the project's `target/`, inside the
code checkout — fine on a laptop, wrong on a server where the checkout is root-owned and the
container runs as uid 50000. Moving target/ out of the checkout is the fix; a reader that
still looks in the old place would capture nothing and say so to nobody.
"""
import re
from pathlib import Path


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


# ==========================================================================================
# THE CASCADE THAT DROPPED A MODEL EVERY TWO HOURS
# ==========================================================================================

MARTS = Path(__file__).resolve().parents[1] / "dbt" / "models" / "marts"


def _materialisation(path: Path) -> str:
    """What a model is materialised as. The project default is `view`, set in
    dbt_project.yml, so a model with no config of its own is a view."""
    match = re.search(r"materialized\s*=\s*'([a-z_]+)'", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "view"


def _parents(path: Path) -> set:
    return set(re.findall(r"ref\('([a-z_]+)'\)", path.read_text(encoding="utf-8")))


def test_no_marts_view_is_built_on_another_marts_view():
    """A VIEW ON A VIEW IS DROPPED WHEN ITS PARENT IS REBUILT, AND TWO DAGS REBUILD THIS
    LINEAGE ON DIFFERENT CLOCKS.

    dbt's Postgres view materialisation renames the old relation to `__dbt_backup`, swaps the
    new one in, and finishes with

        drop view if exists <relation>__dbt_backup cascade

    (dbt/include/postgres/macros/relations/view/drop.sql). Postgres follows the rename on
    every dependent, so the CASCADE takes them with it.

    On 2026-09-04 that meant `cfbd_scores_refresh` — which rebuilds `fct_game_market` every
    two hours as an ancestor of `+srv_game` — silently deleted `int_week_metric_value`, a
    view belonging to `cfbd_lines_snapshot`. That DAG then failed on `dbt test`, twenty
    minutes after its own `dbt run` had created the model, with

        Not able to get columns for unit test 'int_week_metric_value' ...
        because the relation doesn't exist

    Four consecutive runs failed, `publish_distributions` went `upstream_failed` each time,
    and the dead-man's switch sat red — which is worse than the stale panels, because an
    alarm that is always on cannot report anything new.

    NOTHING IN CI COULD SEE IT. CI runs one `dbt build` from empty, in one process, in
    dependency order: the parent is never rebuilt underneath a child there. The interaction
    only exists where two schedules overlap, which is production and nowhere else — the third
    time this project has hit a production-only failure of exactly that shape.

    The rule is cheap and the surface is small: 40 marts models are tables, three are
    incremental, and after the fix no view has a view parent. A table has no dependency to
    cascade through, because its rows are copied at build time.
    """
    views = {p.stem for p in MARTS.glob("*.sql") if _materialisation(p) == "view"}
    assert views, "no marts views found at all — the materialisation parse is wrong"

    offenders = {}
    for path in sorted(MARTS.glob("*.sql")):
        if _materialisation(path) != "view":
            continue
        risky = _parents(path) & views
        if risky:
            offenders[path.stem] = sorted(risky)

    assert not offenders, (
        f"{offenders} — each is a view whose parent is a view. When the parent is rebuilt, "
        f"dbt's `drop view ... cascade` deletes the child. Materialise the child as a table.")


def test_the_model_that_broke_is_specifically_not_a_view_again():
    """Belt and braces on the one that actually failed.

    The rule above is the general guard, and it stops holding the moment `fct_game_market`
    stops being a view — at which point `int_week_metric_value` could quietly revert with the
    general test still green, and the two-hourly failure would come straight back.
    """
    path = MARTS / "int_week_metric_value.sql"
    assert _materialisation(path) == "table", (
        "int_week_metric_value must not be a view: cfbd_scores_refresh rebuilds its parent "
        "fct_game_market every two hours and the cascade deletes it")
