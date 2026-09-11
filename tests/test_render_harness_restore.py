"""R-665 — the harness must put back what it borrowed, and `reload` does not put anything back.

🚨 TWO FAILURE MODES, BOTH MEASURED, AND A FIX FOR EITHER ONE ALONE REOPENS THE OTHER.

  B066  a module left bound to the stub breaks six unrelated tests for the rest of the session.
        The restore exists because of this.
  R-665 `importlib.reload` rebinds a module's globals IN PLACE, so every class it defines
        becomes a NEW object. A file that did `from lib.query import QueryContractError` at
        collection time is left holding a class nothing raises any more. A101 reproduced five
        `test_site_foundation::test_contract_violations_raise` failures on `a68893e` by adding
        a third harness caller — all of which pass when run alone.

⚠️ IT IS ORDER-DEPENDENT, WHICH IS WHY THE SUITE STAYED GREEN. Under pytest-randomly the five
fire only when a harness caller happens to sort BEFORE the victim. That is a coin flip, not a
pass, and these tests are here so the next person does not have to win it.

**This file is also, deliberately, a third harness caller** — the condition that made R-665 fire.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "site"))

import streamlit as real_streamlit                                  # noqa: E402

import render_harness as H                                          # noqa: E402
from lib.query import QueryContractError, check_contract            # noqa: E402


def test_a_class_identity_survives_the_harness():
    """🚨 R-665. `is`, not `==` — the whole defect is two classes with one name.

    The reference is taken at import time, exactly as `test_site_foundation` takes its own, so
    this measures the thing that actually broke rather than a re-import after the fact.
    """
    before = QueryContractError

    with H.streamlit_stubbed() as (_st, _captured, _charts):
        pass

    after = sys.modules["lib.query"].QueryContractError
    assert before is after, (
        "lib.query.QueryContractError is a DIFFERENT class object after the harness ran. "
        "Anything holding the old one — `from lib.query import QueryContractError` at "
        "collection time — will stop matching what check_contract raises. That is R-665, and "
        "it cost five test_site_foundation failures that each passed when run alone.")


def test_pytest_raises_still_matches_after_the_harness():
    """⚠️ THE BEHAVIOUR, NOT JUST THE IDENTITY.

    `is` can hold while the thing a caller depends on breaks, so this asserts the failure mode
    itself: the exception `check_contract` raises must still be the class this file imported.
    It is the exact shape of the five that went red.
    """
    with H.streamlit_stubbed() as (_st, _captured, _charts):
        pass

    with pytest.raises(QueryContractError):
        check_contract("select a from srv_x")          # no LIMIT — AC-G.39


def test_nothing_is_left_bound_to_the_stub():
    """🚨 B066, and it asserts the module's own `st`, not a rendered string.

    ⚠️ BOTH POPULATIONS. `lib.*` is restored by SWAPPING the untouched original back;
    `views.*` is restored by RELOADING in place, because thirteen files hold view module
    objects via `from views import schedule` and a swap would leave them pointing at a
    discarded stub-bound module. Measured on `a68893e`, the views half was never restored at
    all: `views.performance.st` stayed the stub after the context exited.
    """
    # ⚠️ IMPORTED UNDER THE STUB, NOT RENDERED. `H.render` would call the page's real `body()`
    # and read the live warehouse — and a unit test whose outcome depends on whether a database
    # is reachable is the very thing R-662 removed from test_weekly.py this round. Importing
    # the module is all this needs: the binding is set at import, not at render.
    import importlib as _importlib

    with H.streamlit_stubbed() as (stub, _captured, _charts):
        view = _importlib.reload(_importlib.import_module("views.performance"))
        assert view.st is stub, "the view was not bound to the stub inside the context"

    for name in ("lib.query", "lib.states", "lib.table", "views.performance"):
        module = sys.modules.get(name)
        assert module is not None, f"{name} vanished from sys.modules"
        assert module.st is real_streamlit, (
            f"{name}.st is still the harness stub after the context exited. A module left "
            f"bound to the stub breaks every later test that touches it — B066 lost six that "
            f"way, and the restore exists for exactly this.")


def test_the_package_attribute_is_restored_and_not_only_sys_modules():
    """⚠️ `sys.modules` IS NOT THE ONLY HANDLE, and A101's first draft got this wrong.

    Importing `lib.states` also sets `states` as an attribute of the `lib` package, and
    `from lib import states` reads THAT rather than sys.modules. Restoring one and not the
    other hands a caller the stub-bound module while sys.modules says otherwise — which turned
    `test_error_state_never_leaks_internals` red with an empty capture, a failure the fix
    itself introduced.
    """
    import lib

    with H.streamlit_stubbed() as (_st, _captured, _charts):
        pass

    for child in ("query", "states", "table"):
        from_package = getattr(lib, child)
        from_sys_modules = sys.modules[f"lib.{child}"]
        assert from_package is from_sys_modules, (
            f"`from lib import {child}` and `sys.modules['lib.{child}']` are different module "
            f"objects. One of them is the discarded stub-bound copy.")
        assert from_package.st is real_streamlit
