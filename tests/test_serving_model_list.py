"""The static serving list, held against the directory it claims to enumerate. R-714.

`dbt/macros/serving_models.sql` exists so `assert_serving_columns_are_documented` can `ref()` the
layer it checks and be ORDERED after it — see CLAUDE.md §3.6 and the macro's own header. The list
has to be static because dbt collects ref edges at parse time and `graph` is only populated at
execution, which `dim_field_metadata`'s header rules out explicitly.

🚨 THE COST OF A STATIC LIST IS DRIFT, AND THIS FILE IS THE PRICE. A list nobody checks is wrong
the first time somebody adds a serving model — and wrong in the SAFE-LOOKING direction: the new
model simply is not ref'd, the test goes back to running early against a layer that does not
include it, and everything reads green. That is the exact failure R-714 was bought to close,
reintroduced by omission.

The same job `ci/check_publish_build_agreement.py` does for the publish list one layer down.
Asserted on the filesystem, so it needs no database and runs in the `flake8 + pytest` job.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACRO = ROOT / "dbt" / "macros" / "serving_models.sql"
SERVING_DIR = ROOT / "dbt" / "models" / "serving"


def macro_list() -> set:
    """The names the macro returns, read out of its own `return([...])`."""
    text = MACRO.read_text(encoding="utf-8")
    body = re.search(r"return\(\[(.*?)\]\)", text, re.S)
    assert body, "serving_models() no longer returns a list literal; this guard cannot read it"
    names = set(re.findall(r"'(srv_[a-z0-9_]+)'", body.group(1)))
    assert names, "parsed no model names out of serving_models() — an empty scan is not a pass"
    return names


def on_disk() -> set:
    models = {p.stem for p in SERVING_DIR.glob("srv_*.sql")}
    assert models, "found no serving models on disk; this guard is measuring the wrong directory"
    return models


def test_the_macro_lists_every_serving_model_on_disk():
    """A model missing from the list is not ref'd, so the test that depends on the list runs
    before it exists — silently, and green."""
    missing = sorted(on_disk() - macro_list())
    assert not missing, (
        f"serving model(s) on disk but absent from serving_models(): {missing}. "
        f"Until they are added, assert_serving_columns_are_documented is not ordered after them "
        f"and can pass before they are built — CLAUDE.md §3.6.")


def test_the_macro_lists_nothing_that_is_not_there():
    """A phantom name makes `ref()` fail outright rather than silently, so this is the cheaper
    half — but a list that names a deleted model is still a list nobody has read."""
    phantom = sorted(macro_list() - on_disk())
    assert not phantom, (
        f"serving_models() names model(s) that do not exist: {phantom}")


def test_the_documentation_test_refs_the_whole_layer():
    """⚠️ THE LIST BEING RIGHT IS NOT THE SAME AS THE TEST USING IT.

    The edge block is what buys the ordering, and it is four lines of Jinja in a comment that a
    tidy-up could remove without breaking anything visible. This pins that it is still there and
    still unconditional — a `ref()` inside an `{% if %}` is not inferred at all.
    """
    test_sql = (ROOT / "dbt" / "tests" / "assert_serving_columns_are_documented.sql").read_text()
    assert "serving_models()" in test_sql, (
        "the test no longer iterates serving_models(), so it is not ordered after the serving "
        "layer and can pass before the layer exists")
    assert "-- depends_on: {{ ref(model) }}" in test_sql, (
        "the `-- depends_on:` edge block is gone; the refs are what dbt records, not the loop")
