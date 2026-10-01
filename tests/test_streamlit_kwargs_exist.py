"""Every keyword this site passes to Streamlit must exist in the Streamlit that RUNS it.

🚨 WHY THIS FILE EXISTS, AND IT IS A THREE-WEEK OUTAGE ON EVERY GAME PAGE.

B153 shipped `st.container(horizontal=True, wrap=True, gap="medium")` in mid-September.
`wrap` was added to `st.container` AFTER the version `site/requirements.txt` pins, so on the
deployed site that call raised:

    TypeError: LayoutsMixin.container() got an unexpected keyword argument 'wrap'

`states.section` caught it and drew "Could not display this section" — a HANDLED state — so
the Against the Spread panel showed a failure card on every Matchup game page for ~3 weeks.
Marc found it on the live site; A275 diagnosed it (cfdb-main-R-4564).

⚠️ NOTHING IN THE PROJECT COULD SEE IT, AND THAT IS THE POINT:

  - §6.1's render harness STUBS Streamlit, so a stub accepts any keyword and no real
    signature is ever consulted (cfdb-main-R-4565);
  - CI's "site image builds and renders" check loads the app, not every panel's branch;
  - the page returned HTTP 200 and 2,394 tests passed.

A static check needs no server, no browser and no database, and it runs in under a second.

## WHAT THIS COVERS, AND WHAT IT DOES NOT — stated, because an overclaimed guard is worse
## than a narrow one

COVERED:   `st.<name>(..., keyword=...)` where `st` is the module imported as `st` and
           `<name>` is an attribute of it — `st.container`, `st.caption`, `st.metric`, …

NOT COVERED, deliberately, each for a reason:
  - `something.container(width=...)` — a method on a RETURNED object (a column, a container,
    an expander). Its class is not reachable from the source text, and B153's own defect sits
    one line above exactly such a call. A guard that guessed here would be guessing.
  - `st.foo(...)` where `foo` is not an attribute of the module at all — reported as
    unresolvable rather than as a pass, but not failed: it is more likely an alias than a bug.
  - a function declaring `**kwargs`, which accepts anything by construction. There are none
    today; the branch exists so that one appearing does not read as a pass.
  - `**spread` keywords, whose names are not in the source.

## 🚨 AND THE LIMIT THAT MATTERS MOST: THIS CHECKS THE INSTALLED VERSION

The signature consulted is the installed Streamlit's. **This machine's worktrees carry three
different ones — 1.61.1, 1.63.0 and 1.64.0 — and the site pins 1.61.1.** So this guard is
only as good as the version the suite runs against, and `test_the_suite_runs_the_streamlit_the_site_pins`
below says so out loud rather than letting a green run imply more than it measured.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
import streamlit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SITE_REQUIREMENTS = SITE / "requirements.txt"

# 🚨 THE SIGNATURES ARE SNAPSHOTTED AT IMPORT, AND THAT IS NOT TIDINESS — IT IS THE
# DIFFERENCE BETWEEN THIS GUARD WORKING AND SILENTLY CHECKING HALF THE SITE.
#
# 📊 MEASURED WHEN THIS FILE WAS WRITTEN: run alone it inspected 130 calls; run inside the
# full suite it inspected 75, with `st.markdown`, `st.caption` and `st.button` reporting a
# bare `**kwargs`. `site/lib/rawhtml.py` wraps `GUARDED = ("markdown", "caption")` on the
# live module, the wrapper does not carry `functools.wraps`, and only some tests use the
# fixture that puts the originals back. So by the time this test ran, 55 of the site's calls
# were being waved through against a wrapper that accepts anything.
#
# ⚠️ IT WOULD HAVE PASSED. A guard that quietly stops covering 42% of its subject is exactly
# the failure the whole file exists to catch, one level up — and the floor assertion below is
# the only reason it was noticed rather than shipped (R-760).
#
# pytest imports every test module during COLLECTION, before any test runs, so this snapshot
# is taken while the module is still pristine.
_SIGNATURES = {}
for _name in dir(streamlit):
    if _name.startswith("_"):
        continue
    try:
        _SIGNATURES[_name] = inspect.signature(getattr(streamlit, _name))
    except (TypeError, ValueError):
        pass

# A floor, so that both assertions below cannot pass on an empty walk (R-760). Measured at
# 130 when this was written; the floor is deliberately well under it, because the number
# moves with ordinary work and a floor that tracks it exactly is a chore rather than a guard.
MINIMUM_CALLS_INSPECTED = 100


def _pinned_version():
    """The Streamlit the SITE IMAGE installs — `site/requirements.txt`, not the root list."""
    text = SITE_REQUIREMENTS.read_text(encoding="utf-8")
    found = re.search(r"^streamlit==([0-9][^\s#]*)", text, re.MULTILINE)
    return found.group(1) if found else None


def _st_calls():
    """Every `st.<name>(...)` call in `site/`, as (path, lineno, name, [keywords])."""
    for path in sorted(SITE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "st"):
                continue
            # `keyword.arg is None` is `**spread`; its names are not in the source.
            names = [kw.arg for kw in node.keywords if kw.arg is not None]
            if names:
                yield path, node.lineno, func.attr, names


def test_every_streamlit_keyword_exists_in_the_installed_version():
    """🚨 THE GUARD. A keyword Streamlit does not take is a TypeError at render time, and
    `states.section` turns it into a handled failure card rather than a crash — which is why
    three weeks of it looked like a working site.
    """
    offenders = []
    inspected = 0
    unresolvable = []

    for path, lineno, name, keywords in _st_calls():
        signature = _SIGNATURES.get(name)
        if signature is None:
            unresolvable.append(f"{path.relative_to(ROOT)}:{lineno}  st.{name}")
            continue
        parameters = signature.parameters
        if any(p.kind == p.VAR_KEYWORD for p in parameters.values()):
            continue                      # accepts anything; nothing to check
        inspected += 1
        for keyword in keywords:
            if keyword not in parameters:
                offenders.append(
                    f"{path.relative_to(ROOT)}:{lineno}  st.{name}(..., {keyword}=...)  "
                    f"— streamlit {streamlit.__version__} takes "
                    f"{sorted(k for k in parameters)}")

    # ⚠️ ASSERT THE WALK OPENED SOMETHING FIRST. Both assertions pass on an empty walk, and
    # an empty walk is exactly what a renamed directory or a broken glob produces (R-760).
    assert inspected >= MINIMUM_CALLS_INSPECTED, (
        f"only {inspected} st.* calls were inspected, below the floor of "
        f"{MINIMUM_CALLS_INSPECTED} — this guard is not reaching the site's source, so its "
        f"pass means nothing. Unresolvable: {unresolvable}")

    assert not offenders, (
        "a Streamlit keyword argument does not exist in the installed version. At render "
        "time this raises TypeError and `states.section` draws a handled failure card, so "
        "the page returns 200 and the suite stays green while a panel is dead:\n  "
        + "\n  ".join(offenders))


def test_the_suite_runs_the_streamlit_the_site_pins():
    """🚨 THE GUARD ABOVE IS ONLY AS GOOD AS THE VERSION IT RAN AGAINST, AND TODAY THAT IS
    NOT THE VERSION THE SITE RUNS.

    📊 `site/requirements.txt` pins `streamlit==1.61.1` and the site image installs it.
    `requirements.txt:14` says `streamlit>=1.40`, and `requirements-dev.txt` is
    `-r requirements.txt` plus pytest and flake8 — so THE TEST SUITE, in CI and on a laptop,
    resolves whatever is latest. On 2026-10-01 that was 1.63.0 here and 1.64.0 in `wt-c`,
    while production ran 1.61.1.

    🚨 THAT GAP IS THE ROOT CAUSE OF cfdb-main-R-4564, not the `wrap` keyword: B153 wrote a
    call that was valid in the Streamlit it could see and invalid in the one that renders the
    site, and no instrument in the project compared the two.

    ⚠️ THIS SKIPS RATHER THAN FAILS, DELIBERATELY AND VISIBLY. Aligning the two lists is a
    change to `requirements.txt`, which decides what every page and every CI job installs;
    B159 was not authorised to make it and it is not a decision to take in passing. The skip
    names both versions, so it appears in every round's §3.4 skip accounting until someone
    closes it — which is the point. A silent pass here would be the same shape of lie the
    guard above exists to stop.
    """
    pinned = _pinned_version()
    assert pinned, (
        f"no `streamlit==` pin found in {SITE_REQUIREMENTS.relative_to(ROOT)} — the site's "
        f"version is unpinned, which is a bigger finding than anything this file checks")
    if streamlit.__version__ != pinned:
        pytest.skip(
            f"THIS SUITE IS NOT TESTING THE SITE'S STREAMLIT: installed "
            f"{streamlit.__version__}, site/requirements.txt pins {pinned}. The keyword "
            f"guard in this file therefore checked {streamlit.__version__}'s signatures, "
            f"not the ones that will run in production. Align requirements.txt with the "
            f"site pin to make this guard mean what it appears to mean (cfdb-wta-R-2971).")
    assert streamlit.__version__ == pinned
