"""The vendored CFBD spec, and what it is allowed to disagree with the registry about.

`src/endpoints.py` was written by hand from the spec and corrected by probing the live API.
Hand-written against a moving upstream is exactly the pairing that drifts, and until the spec
was committed there was nothing to drift *against* — the reference was a URL, so "the API has
79 paths and we register 74" was not a fact any check could hold.

These tests make the registry and the spec disagree in only one direction, deliberately.
"""
import json
from pathlib import Path

from src.endpoints import BY_PATH, REGISTRY

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config" / "api-docs.json"

# Paths upstream serves that we deliberately do not register yet. Every entry needs a reason,
# because the whole point of this list is that adding to it is a decision someone makes and
# not a test someone silences.
#
# The five `passing/*` endpoints arrived in v5.25.0 and are Priority 6 of prompt 029: they get
# registered with `include=False` and a 2025 floor, backfilled from the CLI rather than swept.
# They are listed here so that a SIXTH new endpoint still fails this test.
# EMPTY, AND THAT IS THE GOAL STATE. Every path the spec serves is registered.
#
# The five passing/* endpoints lived here from the day the spec was vendored — that is what
# surfaced them — until Priority 6 registered them, at which point the "registered AND
# skipped" check below failed and sent me here. Both halves of the guard did their job.
#
# An entry belongs here only when the endpoint is served, known about, and deliberately not
# registered, with the reason written down. It is not a place to park work.
UNREGISTERED_ON_PURPOSE: dict = {}


def spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


def spec_paths() -> set:
    """Spec paths in the registry's own form: no leading slash."""
    return {path.lstrip("/") for path in spec()["paths"]}


def test_the_spec_is_vendored_and_parses():
    """It was gitignored until now, so 'the file is present' was a property of one laptop."""
    assert SPEC_PATH.exists(), (
        "config/api-docs.json is missing. It is vendored deliberately (see .gitignore) — "
        "run scripts/refresh_cfbd_spec.py")
    document = spec()
    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == "College Football Data API"


def test_the_vendored_spec_is_in_normalized_form():
    """The refresh script writes sorted keys at a two-space indent so a real change to one
    endpoint is a few lines and not a reshuffle of five thousand. A hand-edit — or a copy
    dropped in by curl — loses that quietly, and the next diff is unreadable."""
    import scripts.refresh_cfbd_spec as refresh
    assert SPEC_PATH.read_text() == refresh.normalize(spec()), (
        "config/api-docs.json is not in normalized form; regenerate it with "
        "scripts/refresh_cfbd_spec.py rather than editing or curling it into place")


def test_every_registered_endpoint_exists_upstream():
    """A registry entry with no matching spec path is a typo or an endpoint that was removed.
    Either way the sweep spends calls on a 404 and the raw table never appears — which reads
    downstream as "no data for that endpoint yet", the most expensive possible symptom."""
    missing = sorted({e.path for e in REGISTRY} - spec_paths())
    assert not missing, f"registered but not in the spec: {missing}"


def test_new_upstream_endpoints_have_to_be_decided_on():
    """THE DRIFT DETECTOR, AND THE REASON THE SPEC IS COMMITTED.

    CFBD ships endpoints between versions. Registering them is a judgement — cost, scope,
    whether anything downstream wants them — but NOT NOTICING them is not a judgement, and
    that is what a URL reference guaranteed. v5.25.0 added five `passing/*` paths and nothing
    in the repo could have said so.

    A new path fails here until someone either registers it or writes down why not.
    """
    undecided = sorted(spec_paths() - set(BY_PATH) - set(UNREGISTERED_ON_PURPOSE))
    assert not undecided, (
        f"the spec serves endpoints that are neither registered nor deliberately skipped: "
        f"{undecided}. Register them in src/endpoints.py, or add them to "
        f"UNREGISTERED_ON_PURPOSE with the reason.")


def test_the_deliberate_skips_are_all_real_paths():
    """A stale skip is worse than no skip: it silences the drift test for a path that no
    longer exists, and would keep silencing it if upstream reused the name."""
    stale = sorted(set(UNREGISTERED_ON_PURPOSE) - spec_paths())
    assert not stale, f"UNREGISTERED_ON_PURPOSE names paths the spec no longer serves: {stale}"


def test_no_endpoint_is_both_registered_and_deliberately_skipped():
    both = sorted(set(UNREGISTERED_ON_PURPOSE) & set(BY_PATH))
    assert not both, f"registered and also listed as skipped: {both}"
