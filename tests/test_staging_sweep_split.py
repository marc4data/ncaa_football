"""The two halves of the staging uniqueness sweep must partition the list (R-420).

The sweep was one test over 70 models at severity error. Marc split it on 2026-09-08: models
the site depends on keep `error` and gate the publish; warehouse-only models drop to `warn` so
a duplicate in stg_draft_pick cannot freeze a site that never reads it.

THE FAILURE THIS PREVENTS IS SILENT. The split is computed in Jinja from
site_facing_staging(); if the two halves' conditions ever stop being exact complements -- a
typo, an inverted boolean, a third branch -- a model falls out of BOTH and is checked by
nothing, while every test still passes. That is the shape of defect this project keeps
meeting, so it gets a test rather than a comment.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACRO = ROOT / "dbt" / "macros" / "staging_grains.sql"
SITE = ROOT / "dbt" / "tests" / "assert_site_facing_staging_models_are_unique_on_their_grain.sql"
WAREHOUSE = ROOT / "dbt" / "tests" / "assert_warehouse_only_staging_models_are_unique_on_their_grain.sql"


def _listed_models():
    return re.findall(r"\('(stg_[a-z0-9_]+)'", MACRO.read_text())


def test_the_grain_list_lives_in_exactly_one_place():
    """Two copies of the list is how the two halves would drift apart."""
    models = _listed_models()
    assert len(models) > 40, f"only found {len(models)} models — the macro's shape changed"
    for path in (SITE, WAREHOUSE):
        body = path.read_text()
        assert "staging_grains()" in body, f"{path.name} does not read the shared list"
        assert not re.search(r"\('stg_[a-z0-9_]+'\s*,\s*\[", body), \
            f"{path.name} hardcodes its own model list instead of filtering the shared one"


def test_the_two_halves_are_exact_complements():
    """One `== true`, one `== false`, over the same membership call — nothing in neither."""
    site, warehouse = SITE.read_text(), WAREHOUSE.read_text()
    for body in (site, warehouse):
        assert "site_facing_staging()" in body, "membership is not derived from the graph"
    assert "== true" in site.replace(" ", " "), "site-facing half does not select the true branch"
    assert "== false" in warehouse, "warehouse half does not select the false branch"
    assert "== false" not in site, "site-facing half also takes the false branch"
    assert "== true" not in warehouse, "warehouse half also takes the true branch"


def test_the_severities_are_the_ones_marc_ruled_on():
    assert "severity='error'" in SITE.read_text(), "the site-facing half must gate the publish"
    assert "severity='warn'" in WAREHOUSE.read_text(), "the warehouse half must not stop the site"


def test_the_old_single_severity_sweep_is_gone():
    """Leaving it in place would keep the error-everywhere behaviour the split removes."""
    old = ROOT / "dbt" / "tests" / "assert_staging_models_are_unique_on_their_grain.sql"
    assert not old.exists(), "the unsplit sweep is still present and still gates on all 70"
