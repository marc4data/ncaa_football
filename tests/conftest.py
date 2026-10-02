"""Shared test guarantees.

The suite must be runnable offline, for free, and with identical results on a laptop that
happens to have credentials in `.env` and a CI runner that does not. Nothing here is about
convenience — a test that behaves differently depending on ambient environment is a test
that cannot be trusted when it matters.
"""
import os
import sys

import pytest

# Anything whose presence would make a test reach the network or spend money. The values
# live in `.env`, which `load_dotenv()` reads at import time in several modules, so simply
# not exporting them in the shell is not enough.
AMBIENT_CREDENTIALS = (
    "ANTHROPIC_API_KEY",
    "CFBD_API_KEY",
    "DATABRICKS_TOKEN",
    "DATABRICKS_SERVER_HOSTNAME",
    "DATABRICKS_HTTP_PATH",
    "ALERT_SMTP_HOST",
    "ALERT_EMAIL_FROM",
    "ALERT_EMAIL_TO",
)


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch):
    """Strip real credentials from every test.

    Added after `ANTHROPIC_API_KEY` landed in `.env` and the suite silently started making
    a live, billable call to the Anthropic API on every run — 11.5 seconds in one test that
    had previously taken milliseconds. It still *passed*, which is the worrying part: the
    failure mode was a slow, paid, network-dependent suite that looked entirely healthy.

    A test that wants a credential sets it explicitly with `monkeypatch.setenv`, which
    still works because this runs first and only removes what it did not put there.
    """
    for name in AMBIENT_CREDENTIALS:
        monkeypatch.delenv(name, raising=False)
    # `load_dotenv` does not override variables that already exist, so a sentinel value
    # blocks a re-read from repopulating one mid-test.
    monkeypatch.setenv("DOTENV_DISABLED_FOR_TESTS", "1")


@pytest.fixture
def assert_no_network(monkeypatch):
    """Fail loudly if a test opens a socket, for tests that must prove they stay local."""
    import socket

    def refuse(*_args, **_kwargs):
        raise AssertionError("this test attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return True


def pytest_configure(config):
    os.environ.setdefault("TZ", "UTC")

# ══════════════════════════════════════════════════════════════════════════════════════════
# 🚨 A277 (cfdb-main-R-4622) — NO TEST LEAVES STREAMLIT PATCHED FOR THE NEXT ONE
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# 📊 B159 MEASURED THE DAMAGE AND THE NUMBER IS THE POINT: its signature guard inspected 130
# calls run alone and **75 inside the full suite**. 55 of the site's calls were being checked
# against a wrapper instead of against Streamlit.
#
# `site/lib/rawhtml.py`'s `install()` mutates a third-party class attribute and a module
# attribute. ⚠️ **`site/app.py:41` CALLS IT**, so every test that executes or imports the app —
# the tab-title test, the render harness, anything that reaches `app.py` — installs the guard
# globally and never puts it back. `tests/test_raw_html_blank_lines.py` has a `guarded` fixture
# that restores correctly, but it only covers the tests that ask for it.
#
# ✅ SO THE RESTORE MOVES HERE, WHERE IT CANNOT BE FORGOTTEN. Autouse, so a test that installs
# the guard cannot contaminate the next one whatever route it took to install it.
#
# ⚠️ IT IS A RESTORE, NOT AN UNINSTALL, AND NOT AN INSTALL. It puts back exactly what was there
# when the test started — which is the right behaviour in both directions and leaves
# `test_raw_html_blank_lines.py`'s own narrower fixture correct rather than redundant.
#
# ⚠️ AND IT TOUCHES NOTHING IF STREAMLIT IS NOT LOADED. `sys.modules.get` rather than an import:
# `tests/test_tab_title.py` runs `app.py` against a deliberately minimal STUB streamlit, and a
# conftest that forced the real import would change what that test is testing.


_GUARDED_FALLBACK = ("markdown", "caption")


def _guarded_names():
    """The names `rawhtml` patches — from the module itself when it is loaded (R-574).

    ⚠️ A SECOND COPY OF THAT LIST WOULD BE FREE TO DISAGREE, so the fallback below is pinned to
    `rawhtml.GUARDED` by `test_raw_html_blank_lines.py` rather than left to drift. The fallback
    exists only because this fixture must not force `site/` onto `sys.path` at collection time.
    """
    module = sys.modules.get("lib.rawhtml")
    names = getattr(module, "GUARDED", None) if module else None
    return tuple(names) if names else _GUARDED_FALLBACK


@pytest.fixture(autouse=True)
def streamlit_is_handed_back_unpatched():
    """Snapshot Streamlit's guarded bindings, and put them back after the test."""
    streamlit = sys.modules.get("streamlit")
    if streamlit is None:
        yield
        return
    try:
        from streamlit.delta_generator import DeltaGenerator   # noqa: PLC0415
    except Exception:                                          # pragma: no cover
        DeltaGenerator = None

    saved = []
    for name in _guarded_names():
        for owner in (DeltaGenerator, streamlit):
            if owner is not None and hasattr(owner, name):
                saved.append((owner, name, getattr(owner, name)))
    yield
    for owner, name, original in saved:
        if getattr(owner, name, None) is not original:
            setattr(owner, name, original)
