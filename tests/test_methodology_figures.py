"""Every number printed on the Methodology page, re-measured against the repository.

🚨 THIS FILE IS WHY THE PAGE MAY PRINT COUNTS AT ALL (A233, cfdb-main-R-3114).

**A stale number on the Methodology page is worse than no number**, because that page's whole
claim is that the site can be audited. A figure nobody re-measures is an assertion with a
decimal point — which is the thing the page's own docstring says it exists to avoid.

⚠️ SO THE FIGURES ARE DATED LITERALS AND THIS IS THE GUARD. A change that makes one wrong
fails CI rather than sitting on the page looking authoritative.

⚠️ AND EVERY MEASUREMENT HERE READS A STRUCTURED SOURCE, NEVER A GREP. B154 reported ~2,474
schema tests from a count of `name:` lines — documented COLUMNS — when the real number is 510.
R-859: how many lines matched is not how many tests. The dbt figures come from the compiled
manifest, the endpoints from the registry object, the pages from `registry.PAGES`, and the
test count from pytest's own collection.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site"))

PAGE = (ROOT / "site" / "views" / "methodology.py").read_text(encoding="utf-8")
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"


def _printed(label: str) -> list:
    """Every bolded number on the page's row for `label`.

    The figures live in a markdown table, so the row is the unit. Returning ALL of a row's
    bold numbers means a row carrying two counts is checked on both.
    """
    for line in PAGE.splitlines():
        if line.lstrip().startswith("|") and label in line:
            return [int(n.replace(",", "")) for n in re.findall(r"\*\*([\d,]+)\*\*", line)]
    raise AssertionError(f"the page has no table row containing {label!r}")


@pytest.fixture(scope="module")
def manifest():
    if not MANIFEST.exists():
        pytest.skip("no compiled dbt manifest — run `dbt parse` (§3.4)")
    return json.loads(MANIFEST.read_text())


def test_the_page_dates_its_counts():
    """⚠️ THE DATE IS NOT DECORATION. The test keeps a figure TRUE; the date keeps it HONEST
    for a reader, who cannot see the test and is entitled to know the count was taken at a
    moment rather than computed as they look at it."""
    import importlib
    methodology = importlib.import_module("views.methodology")
    assert re.fullmatch(r"[A-Z][a-z]+ \d{4}", methodology.SCALE_AS_OF), methodology.SCALE_AS_OF
    assert methodology.SCALE_AS_OF in PAGE or "SCALE_AS_OF" in PAGE


def test_the_endpoint_counts_are_the_registrys_own(manifest):
    """📊 TWO NUMBERS, BECAUSE THE REGISTRY HOLDS MORE THAN IT FETCHES. Printing only the
    larger one would overstate what the pipeline actually pulls — `include=False` is a real
    flag with 23 endpoints behind it, and §2.5's own warning is that an endpoint nothing
    fetches produces models that are correct and empty."""
    from src.endpoints import REGISTRY
    total, fetched = _printed("ingestion registry")
    assert total == len(REGISTRY), f"page says {total}, registry has {len(REGISTRY)}"
    real = len([e for e in REGISTRY if e.include])
    assert fetched == real, f"page says {fetched} fetched, registry has {real}"


def test_the_model_counts_are_the_manifests_own(manifest):
    models = [n for n in manifest["nodes"].values() if n["resource_type"] == "model"]
    layers = {}
    for n in models:
        layers[n["fqn"][1]] = layers.get(n["fqn"][1], 0) + 1
    total, staging, marts, serving = _printed("dbt models")
    assert total == len(models), f"page says {total}, manifest has {len(models)}"
    assert staging == layers.get("staging"), layers
    assert marts == layers.get("marts"), layers
    assert serving == layers.get("serving"), layers
    assert staging + marts + serving == total, "the layers must add up to the total printed"


def test_the_test_counts_are_the_manifests_own(manifest):
    """🚨 THE SPLIT IS THE INFORMATIVE PART. 650 alone reads as one kind of thing; 510 schema
    tests and 140 hand-written assertions says what kind of checking this project does."""
    tests = [n for n in manifest["nodes"].values() if n["resource_type"] == "test"]
    singular = [n for n in tests if n.get("test_metadata") is None]
    generic = [n for n in tests if n.get("test_metadata") is not None]
    total, schema, hand = _printed("dbt data tests")
    assert total == len(tests), f"page says {total}, manifest has {len(tests)}"
    assert schema == len(generic), f"page says {schema} schema, manifest has {len(generic)}"
    assert hand == len(singular), f"page says {hand} hand-written, manifest has {len(singular)}"


def test_the_page_count_is_the_registrys_own():
    from lib import registry
    (printed,) = _printed("Pages on this site")
    assert printed == len(registry.PAGES), (
        f"page says {printed}, registry.PAGES has {len(registry.PAGES)}")


def test_the_python_test_figure_is_a_FLOOR_and_the_floor_holds():
    """⚠️ A FLOOR RATHER THAN AN EXACT COUNT, DELIBERATELY.

    An exact number would be wrong the moment anybody adds a test — which is every round — so
    the page says "more than" and this asserts the floor. **A figure that forces a page edit
    on every unrelated round is a figure that will eventually be edited without being
    re-measured**, which is the failure this whole file exists to prevent.

    🚨 AND THE FLOOR MUST NOT DRIFT SO FAR BELOW THE TRUTH THAT IT STOPS MEANING ANYTHING.
    The upper bound keeps it honest in the other direction: once the suite has grown well
    past the printed floor, this fails and the page gets a new, larger, still-true number.
    """
    match = re.search(r"more than \*\*([\d,]+)\*\*", PAGE)
    assert match, "the page no longer states the test count as a floor"
    floor = int(match.group(1).replace(",", ""))
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                           "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    collected = re.search(r"(\d+) tests? collected", done.stdout)
    assert collected, done.stdout[-400:]
    actual = int(collected.group(1))
    assert actual > floor, f"the page claims more than {floor}; pytest collects {actual}"
    assert actual < floor * 1.25, (
        f"pytest collects {actual} against a printed floor of {floor} — the floor has drifted "
        f"far enough below the truth to be uninformative. Raise it.")


def test_the_page_claims_no_uptime_and_no_reliability_percentage():
    """🚨 NO SENTENCE THAT THE NEXT OUTAGE WOULD FALSIFY. The site went stale on seven days
    this month; the page's credibility comes from saying what happens when a build is wrong,
    not from implying nothing breaks."""
    for bad in ("uptime", "99.", "always available", "never fails", "zero downtime",
                "100% of the time"):
        assert bad.lower() not in PAGE.lower(), f"the page claims {bad!r}"


def test_the_page_does_not_republish_the_withdrawn_models_figures():
    """⚠️ THE POINT IS THE WITHDRAWAL, NOT THE NUMBER THAT WAS WRONG. Printing 72.5% again —
    even to disown it — puts the leaked figure back on the site in bold."""
    assert "72.5" not in PAGE, "the leaked moneyline figure is back on the page"
    # ⚠️ R-2260 — A SUBSTRING IS NOT A RULE. The first draft of this banned "hit rate" and
    # failed on the page's own long-standing and correct sentence, *"a backtest hit rate and
    # a realised hit rate are different claims"*. What is forbidden is a PERCENTAGE offered
    # as one of the withdrawn models' results, not the words used to discuss accuracy.
    withdrawn_context = [line for line in PAGE.splitlines()
                         if "withdraw" in line.lower() or "closing spread" in line.lower()]
    for line in withdrawn_context:
        assert not re.search(r"\d+(\.\d+)?\s*%", line), (
            f"a withdrawn model's figure is republished: {line.strip()[:90]}")


def test_the_page_does_not_contradict_the_live_withdrawal_note():
    """`lib/models.WITHDRAWAL_NOTE` is on the site today. Two descriptions of one decision are
    two things that can drift, so the page must agree with it on the facts that matter."""
    from lib import models
    assert len(models.WITHDRAWN) == 6 and len(models.PUBLISHED) == 1, (
        "the withdrawal changed shape; the Methodology wording says six of seven")
    assert "six" in PAGE.lower()
    # both say the data still exists
    assert "deleted" in PAGE.lower() or "warehouse" in PAGE.lower()
    assert "deleted" in models.WITHDRAWAL_NOTE.lower()


def test_the_page_states_the_gate_and_what_it_costs():
    """The honest framing is the strong one: a gated publish means stale data, and saying so
    is more credible than implying nothing ever breaks."""
    low = PAGE.lower()
    assert "gated" in low or "gate" in low
    assert "yesterday" in low, "the page must say what a failed check actually costs a reader"
    assert "dead-man" in low or "heartbeat" in low
