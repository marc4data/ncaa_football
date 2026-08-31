"""The grain sweep has to keep covering the class, not just the models it shipped with.

`row_number() over (partition by params ...)` keeps the newest response PER REQUEST. That is
correct only while different requests return disjoint entities. It held for /games until a
season-scoped fetch was added beside the week-scoped ones; the two overlapped, params-level
dedup could not see it, and 211 duplicate game_ids reached fct_game.

Six outages in four days came from patching one instance of a defect class at a time. The
lesson recorded then was to enumerate the class. A sweep that enumerates the class as of the
day it was written decays into a per-model test the moment someone adds the eighth model, so
this asserts the enumeration is still complete.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "dbt" / "models" / "staging"
GRAIN_TEST = ROOT / "dbt" / "tests" / "assert_staging_models_are_unique_on_their_grain.sql"

# Models whose grain is genuinely not one row per anything, with the reason. Adding to this is
# a decision; forgetting to add a model is not.
GRAIN_EXEMPT = {
    "stg_lines": "one row per (game, provider, SNAPSHOT) — repeated fetches are the point, "
                 "because /lines returns only opening and current and movement between them "
                 "cannot be backfilled",
}


def params_deduped_models() -> set:
    """Staging models that resolve raw multiplicity by partitioning on `params`."""
    found = set()
    for sql_file in sorted(STAGING.glob("*.sql")):
        text = sql_file.read_text()
        if re.search(r"partition\s+by\s+params", text):
            found.add(sql_file.stem)
    return found


def enumerated_in_grain_test() -> set:
    body = GRAIN_TEST.read_text()
    listing = body[body.index("set staging_grains"):body.index("%}", body.index("set staging_grains"))]
    return set(re.findall(r"\('(stg_[a-z_]+)'", listing))


def test_the_grain_sweep_exists():
    assert GRAIN_TEST.exists()


def test_every_params_deduped_model_declares_a_grain():
    """This is the guard that keeps the sweep a class-level test.

    A model that partitions by params has the /games failure available to it by construction.
    If it is not in the sweep, the day someone adds a season-scoped fetch beside a week-scoped
    one, the duplicates reach the marts exactly as they did before — and the sweep will report
    green, because it is only looking at the models it happened to be written with.
    """
    missing = params_deduped_models() - enumerated_in_grain_test() - set(GRAIN_EXEMPT)
    assert not missing, (
        f"these staging models dedup on `params` but declare no grain: {sorted(missing)}. "
        f"Add them to assert_staging_models_are_unique_on_their_grain.sql, or to "
        f"GRAIN_EXEMPT here with the reason.")


def test_the_grain_sweep_names_only_real_models():
    """A grain declared for a model that no longer exists fails the dbt run at ref() time, but
    it fails as a compilation error two layers from the cause. Naming it here is cheaper."""
    existing = {f.stem for f in STAGING.glob("*.sql")}
    unknown = enumerated_in_grain_test() - existing
    assert not unknown, f"grain sweep references non-existent models: {sorted(unknown)}"


def test_the_exemptions_are_still_real_models():
    existing = {f.stem for f in STAGING.glob("*.sql")}
    stale = set(GRAIN_EXEMPT) - existing
    assert not stale, f"GRAIN_EXEMPT names models that no longer exist: {sorted(stale)}"


def test_the_new_family_models_declare_their_grain():
    """The three models this sweep was extended for. Named explicitly so a refactor that drops
    one from the enumeration fails here rather than going quiet."""
    enumerated = enumerated_in_grain_test()
    assert {"stg_game_weather", "stg_game_team_stat", "stg_game_player_stat"} <= enumerated
