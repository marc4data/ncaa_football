"""A stale compiled manifest must FAIL, not quietly skip (R-462).

WHAT THIS EXISTS TO CATCH. Four tests in test_dag_structure.py read
`dbt/target/manifest.json` and skip themselves when it is older than the dbt sources it
describes. That skip is correct — reading a stale artifact would assert against a project
that no longer exists — but it is SILENT. B072 edited two dbt models and watched the suite
go from 820 passed / 3 skipped to 816 passed / 7 skipped, which reads as green.

A suite that quietly tests less after a model change is the worst shape a guard can take:
the developer who most needs those four assertions — the one who just edited a model — is
exactly the one who stops getting them.

B072's remedy was "run `dbt parse` after any model edit before trusting a local green".
That is a checklist item, and this project's standing doctrine is that the hand step is the
one that gets skipped. This is the same instruction as a guard.

⚠️ AN ABSENT MANIFEST IS NOT A FAILURE, AND BREAKING THAT CASE WOULD BE WORSE THAN THE
PROBLEM. A fresh checkout has no `dbt/target/` at all, and B069 measured exactly that as
four of the ±5 drift in the suite total. CI's `flake8 + pytest` job runs no dbt step, so the
manifest is absent there and this skips; the `dbt build` job runs no pytest. This guard
therefore fires only where the condition it describes can actually mislead someone: a local
working copy that has compiled once and has been edited since.

It deliberately reuses test_dag_structure's definition of stale — .sql files plus
dbt_project.yml — so that it fails in precisely the case that makes those four skip, and
never in a case that does not. ⚠️ That definition does NOT include _models.yml: editing a
description or a test there also changes the manifest and does not mark it stale. That is a
real gap, it is inherited rather than introduced here, and widening it is a separate call.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"


def _sources_newer_than_manifest():
    """The dbt sources modified since the manifest was compiled, newest first."""
    compiled = MANIFEST.stat().st_mtime
    candidates = list((ROOT / "dbt").rglob("*.sql")) + [ROOT / "dbt" / "dbt_project.yml"]
    newer = [f for f in candidates if f.exists() and f.stat().st_mtime > compiled]
    return sorted(newer, key=lambda f: f.stat().st_mtime, reverse=True)


def test_the_compiled_manifest_is_not_older_than_the_models_it_describes():
    """The guard. A stale manifest fails here instead of silently thinning the suite."""
    if not MANIFEST.exists():
        # THE LEGITIMATE CASE. A fresh checkout, or CI's pytest job, has never compiled.
        # Nothing is being hidden, because nothing was ever there to go stale.
        pytest.skip(
            "no compiled manifest — nothing has been compiled in this working copy, so "
            "nothing is stale. This is the fresh-checkout case and it is not a failure.")

    newer = _sources_newer_than_manifest()
    if not newer:
        return

    listed = "\n".join(f"    {f.relative_to(ROOT)}" for f in newer[:10])
    more = f"\n    … and {len(newer) - 10} more" if len(newer) > 10 else ""
    pytest.fail(
        "dbt/target/manifest.json is OLDER than the dbt sources it describes, so every test "
        "that reads it has silently skipped itself and this suite is testing less than its "
        "pass count suggests.\n\n"
        f"Modified since the last compile ({len(newer)} file(s)):\n{listed}{more}\n\n"
        "Fix it with:\n"
        "    cd dbt && dbt parse\n\n"
        "`dbt parse` needs no database connection and no warehouse tunnel. Re-run the suite "
        "afterwards; the four test_dag_structure tests that read the manifest will run again.")
