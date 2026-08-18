"""Shared test guarantees.

The suite must be runnable offline, for free, and with identical results on a laptop that
happens to have credentials in `.env` and a CI runner that does not. Nothing here is about
convenience — a test that behaves differently depending on ambient environment is a test
that cannot be trusted when it matters.
"""
import os

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
