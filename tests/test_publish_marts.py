"""The last hop before a user sees data, and the one that took the site down.

On 29 August the 20:00 restore was killed 34 minutes in. `pg_dump --clean` had already
dropped every serving table, psql autocommits statement by statement, so the drops were
committed and the site served nothing from 20:14 until 21:00 — in the middle of a game day.
`ON_ERROR_STOP=1` was already set and did not help: it stops on error, it does not undo what
has committed.

These pin the two properties that make that impossible rather than unlikely.
"""
import subprocess
from pathlib import Path

import pytest

from src import publish_marts

REMOTE_SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "cfdb_publish.sh"


def _code(text: str) -> str:
    """Shell source with comment lines removed.

    The fourth time in this repo a source-reading test has matched its own prose: the first
    version of the count assertion below found two occurrences, one of which was the comment
    explaining the flag. Strip the commentary and assert on the code.
    """
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _restore_block() -> str:
    """The body of the `restore)` case in the forced command."""
    src = _code(REMOTE_SCRIPT.read_text())
    start = src.index("    restore)")
    return src[start:src.index(";;", start)]


def test_the_remote_restore_runs_in_one_transaction():
    """Postgres has transactional DDL, so a restore inside a transaction keeps readers on
    the OLD tables until commit and rolls back to them on failure. Without it, every publish
    is a window where the live site reads empty tables, and a failed publish makes that
    window permanent."""
    block = _restore_block()
    assert "--single-transaction" in block, (
        "the restore must be atomic: without it a killed restore leaves the serving "
        "database holding dropped tables and the site serves nothing")


def test_the_restore_is_the_only_verb_that_needs_the_transaction():
    """A guard against pasting the flag somewhere it does nothing. `count` and `grant` are
    single statements; wrapping them would only obscure what the flag is for."""
    assert _code(REMOTE_SCRIPT.read_text()).count("--single-transaction") == 1


def test_a_hanging_publish_raises_instead_of_running_forever(monkeypatch):
    """34 minutes is long past Airflow's task-heartbeat timeout, so the worker was killed
    without a traceback and the retry waited out its own delay on top. A bounded failure is
    what makes the retry — the thing that actually recovered the site — start promptly."""
    monkeypatch.setattr(publish_marts, "PUBLISH_KEY", "/tmp/key")
    monkeypatch.setattr(publish_marts, "PUBLISH_HOST", "user@host")

    def hang(*_a, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(publish_marts.subprocess, "run", hang)
    with pytest.raises(RuntimeError) as excinfo:
        publish_marts._publish_ssh("restore serving", stdin=b"x")
    message = str(excinfo.value)
    assert "timed out" in message
    # The message must say the site is intact, because the first question at 21:00 on a
    # Saturday is "is the site down", not "which subprocess failed".
    assert "rolled back" in message


def test_the_restore_gets_a_longer_budget_than_the_cheap_verbs(monkeypatch):
    """`count` answers in seconds; only the restore streams 333 MB. One shared timeout would
    either strangle the restore or let a hung count sit for twelve minutes."""
    seen = {}
    monkeypatch.setattr(publish_marts, "PUBLISH_KEY", "/tmp/key")
    monkeypatch.setattr(publish_marts, "PUBLISH_HOST", "user@host")
    monkeypatch.setattr(publish_marts.subprocess, "run",
                        lambda *a, **k: seen.update(k) or subprocess.CompletedProcess(a, 0, b"", b""))

    publish_marts._publish_ssh("count serving srv_scoreboard")
    quick = seen["timeout"]
    publish_marts._publish_ssh("restore serving", stdin=b"dump")
    assert seen["timeout"] > quick
    assert quick == publish_marts.QUICK_VERB_TIMEOUT_SECONDS


def test_the_publish_timeout_stays_under_the_two_hour_cadence():
    """The scores DAG publishes every two hours with two retries. A timeout long enough to
    let attempts overlap would queue publishes behind each other."""
    total = publish_marts.PUBLISH_TIMEOUT_SECONDS * 3
    assert total < 2 * 60 * 60
