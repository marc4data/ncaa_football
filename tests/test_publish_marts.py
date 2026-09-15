"""The last hop before a user sees data, and the one that took the site down.

On 29 August the 20:00 restore was killed 34 minutes in. `pg_dump --clean` had already
dropped every serving table, psql autocommits statement by statement, so the drops were
committed and the site served nothing from 20:14 until 21:00 — in the middle of a game day.
`ON_ERROR_STOP=1` was already set and did not help: it stops on error, it does not undo what
has committed.

These pin the two properties that make that impossible rather than unlikely.
"""
import subprocess
import sys
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


def test_only_the_restore_verbs_wrap_themselves_in_a_transaction():
    """A guard against pasting the flag somewhere it does nothing. `count`, `grant` and
    `ensure-schema` are single statements; wrapping them would only obscure what the flag is
    for. Both restore verbs need it — the compressed one is the same restore.

    Asserted per verb rather than as a total count, which was the first version and broke
    the moment a second legitimate restore verb appeared.
    """
    script = _code(REMOTE_SCRIPT.read_text())
    wrapped, bare = [], []
    for verb in ("ping", "ensure-schema", "restore", "restore-gz", "grant", "count"):
        start = script.index(f"    {verb})")
        block = script[start:script.index(";;", start)]
        (wrapped if "--single-transaction" in block else bare).append(verb)
    assert wrapped == ["restore", "restore-gz"], wrapped
    assert set(bare) == {"ping", "ensure-schema", "grant", "count"}


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

    publish_marts._publish_ssh("count serving srv_game")
    quick = seen["timeout"]
    publish_marts._publish_ssh("restore serving", stdin=b"dump")
    assert seen["timeout"] > quick
    assert quick == publish_marts.QUICK_VERB_TIMEOUT_SECONDS


def test_the_publish_timeout_stays_under_the_two_hour_cadence():
    """The scores DAG publishes every two hours with two retries. A timeout long enough to
    let attempts overlap would queue publishes behind each other."""
    total = publish_marts.PUBLISH_TIMEOUT_SECONDS * 3
    assert total < 2 * 60 * 60


# --- the wire is the bottleneck -----------------------------------------------------------

def test_the_dump_is_compressed_before_it_crosses_the_wire(monkeypatch):
    """Measured: a 334 MB dump over a ~20 Mbit/s link is 135 seconds, which is essentially
    the whole publish. The database work is not the cost; the upload is.

    That is why the job is fragile. When the link is busy the same publish takes 13 to 17
    minutes — long enough for Airflow to disown the task as a zombie and kill it mid-stream,
    which Postgres then reports as a truncated COPY at a random line.
    """
    import gzip
    sent = {}
    monkeypatch.setattr(publish_marts, "PUBLISH_KEY", "/tmp/key")
    monkeypatch.setattr(publish_marts, "PUBLISH_HOST", "user@host")

    def _record(verb, stdin=b"", stdin_file=None):
        # A137: the restore now hands ssh a FILE rather than a buffer. Read it here so the
        # assertion below still checks the bytes that would cross the wire.
        payload = Path(stdin_file).read_bytes() if stdin_file is not None else stdin
        sent.update(verb=verb, stdin=payload, streamed=stdin_file is not None)
        return subprocess.CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(publish_marts, "_publish_ssh", _record)

    body = b"COPY serving.srv_game FROM stdin;\n" + b"row\tdata\n" * 5000
    publish_marts.restore_to_serving(body, "serving")

    assert sent["verb"] == "restore-gz serving", (
        "the plain `restore` verb sends the dump uncompressed over the link that is already "
        "the failure point")
    assert sent["streamed"], (
        "A137: the payload must reach ssh as a file. Handing it over as bytes is the OOM "
        "that took the weekly publish down on 2026-09-15")
    assert gzip.decompress(sent["stdin"]) == body, "the remote must receive the same bytes"
    assert len(sent["stdin"]) < len(body), "compression must actually shrink the payload"


# --- the dump must never become a Python object (A137, cfdb-main-R-914) --------------------

def test_the_dump_never_becomes_a_python_object(tmp_path, monkeypatch):
    """🚨 THE OOM THAT TOOK THE WEEKLY PUBLISH DOWN, PINNED AS A MEASUREMENT.

    On 2026-09-15 `cfbd_pregame_refresh.publish_to_serving` was SIGKILLed on all three
    attempts at `[serving] publishing 34 table(s)`. No dbt test failed — that run captured
    498 pass, 4 warn, 0 fail. The serving dump measures 1,671,065,249 bytes and the droplet
    has 3.9 GB with 1.8 GB already in use, and the old code held the dump as `bytes` twice
    over: `capture_output=True` peaks at about 2x while joining the chunks, then
    `gzip.compress(dump)` allocates the compressed copy beside the live original.

    ⚠️ THIS IS A REAL MEASUREMENT AND NOT A STRUCTURAL ONE. It runs a fake `pg_dump` that
    emits 64 MB and asserts the Python heap never grows to hold it. Under the old
    implementation the peak was the whole payload; under this one it is one chunk.
    """
    import tracemalloc

    payload_mb = 64
    faker = tmp_path / "fake_pg_dump.py"
    faker.write_text(
        "import sys\n"
        "block = b'x' * (1 << 20)\n"
        f"for _ in range({payload_mb}):\n"
        "    sys.stdout.buffer.write(block)\n"
    )
    monkeypatch.setattr(publish_marts, "_pg_dump_binary", lambda: sys.executable)
    monkeypatch.setattr(publish_marts, "_local_psql_args", lambda: [str(faker)])
    monkeypatch.setattr(publish_marts, "local_pg_env", dict)

    sink = tmp_path / "dump.sql"
    tracemalloc.start()
    written = publish_marts.dump_marts_to_file(["srv_game"], sink, "serving")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert written == payload_mb * (1 << 20), "the whole dump must reach the file"
    assert peak < 8 * (1 << 20), (
        f"the dump was held in memory: peak {peak / 1e6:.1f} MB for a "
        f"{payload_mb} MB dump. capture_output=True is how the publish died")


def test_the_compressor_streams_too(tmp_path):
    """The second doubling. `gzip.compress(blob)` needs the input in memory and allocates the
    output beside it; fixing only the dump would have moved the OOM four lines down."""
    import gzip
    import tracemalloc

    source = tmp_path / "big.sql"
    with open(source, "wb") as handle:
        for _ in range(64):
            handle.write(b"COPY serving.srv_game FROM stdin;\n" * 16384)
    target = tmp_path / "big.sql.gz"

    tracemalloc.start()
    packed = publish_marts._gzip_file(source, target)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert packed == target.stat().st_size
    assert gzip.decompress(target.read_bytes()) == source.read_bytes(), "same bytes"
    assert peak < 8 * (1 << 20), (
        f"the compressor held the payload: peak {peak / 1e6:.1f} MB for a "
        f"{source.stat().st_size / 1e6:.1f} MB input")


def test_the_spool_is_not_a_ram_disk_by_default(monkeypatch):
    """⚠️ A127 found `/dev/shm` breaking a rebuild for exactly this reason: a tmpfs looks like
    a directory and spends memory. Spooling 1.67 GB into one would reproduce the OOM with the
    fix in place, which is the worst possible outcome — it would look fixed."""
    monkeypatch.delenv("CFDB_PUBLISH_SPOOL_DIR", raising=False)
    assert publish_marts._spool_dir() is None, (
        "the default must be the platform temp directory, which is disk-backed")
    monkeypatch.setenv("CFDB_PUBLISH_SPOOL_DIR", "/var/tmp")
    assert publish_marts._spool_dir() == "/var/tmp", "the override must be honored"


def test_the_remote_understands_the_compressed_verb():
    """Client and forced command have to agree, and they are deployed separately — the
    script goes to the droplet by scp, the Python by the Airflow worktree. A mismatch is a
    refused verb at publish time."""
    script = _code(REMOTE_SCRIPT.read_text())
    assert "restore-gz)" in script
    assert "gunzip" in script


def test_the_compressed_restore_is_still_atomic():
    """The new path must not quietly lose the property that keeps the site up. Both restore
    verbs wrap their load in one transaction."""
    script = _code(REMOTE_SCRIPT.read_text())
    start = script.index("    restore-gz)")
    block = script[start:script.index(";;", start)]
    assert "--single-transaction" in block


# --- the two-hourly publish must stay small ------------------------------------------------

def test_the_heavy_player_tables_are_excluded_from_the_hot_publish():
    """The scores DAG publishes serving every two hours, and the upload is the fragile step.

    srv_player_stats, srv_player_game_log and srv_player_play are 608 MB of the serving
    schema's 932 MB — measured, not estimated — and including them takes the payload from
    59 MB to 182 MB gzipped. On a link where 59 MB has already taken 13 to 17 minutes, that
    is the difference between an occasional zombie kill and a routine one.
    """
    from src import publish_marts
    assert set(publish_marts.HOT_SERVING).isdisjoint(publish_marts.HEAVY_SERVING)
    for table in ("srv_player_stats", "srv_player_game_log", "srv_player_play"):
        assert table in publish_marts.HEAVY_SERVING
        assert table not in publish_marts.HOT_SERVING


def test_the_full_publish_still_ships_everything():
    """Splitting must not quietly turn "publish everything" into a subset. A table that is in
    neither list would never reach the site, and the failure would look like a stale page
    rather than a missing publish."""
    from src import publish_marts
    assert (set(publish_marts.DEFAULT_SERVING)
            == set(publish_marts.HOT_SERVING) | set(publish_marts.HEAVY_SERVING))


def test_the_scores_dag_asks_for_the_hot_publish_and_the_weekly_one_does_not():
    """The cadence split only works if the callers agree with it. Asserted on source because
    both are lambdas inside a DAG definition."""
    scores = Path(__file__).resolve().parents[1] / "dags" / "scores_refresh_dag.py"
    weekly = Path(__file__).resolve().parents[1] / "dags" / "weekly_refresh_dag.py"
    scores_src = _code(scores.read_text())
    assert "hot=True" in scores_src, (
        "the two-hourly publish must ship only the hot tables")
    assert "hot=True" not in _code(weekly.read_text()), (
        "the weekly publish is where the heavy player tables reach the site; if it also "
        "asked for the hot set they would never be published at all")


def test_every_serving_model_in_the_project_is_published():
    """A serving model that is in neither publish list never reaches the site.

    The failure mode is quiet and slow: dbt builds the table happily, the warehouse has it,
    the documentation test counts its columns, and the page reading it renders Degraded
    forever with nothing in any log to explain why. srv_game_weather was one edit away from
    exactly that.

    Checked against the model files rather than the database, so it fails in CI on the pull
    request that adds a model rather than after a deploy.
    """
    from pathlib import Path
    from src import publish_marts
    models = Path(__file__).resolve().parents[1] / "dbt" / "models" / "serving"
    on_disk = {p.stem for p in models.glob("srv_*.sql")}
    published = set(publish_marts.DEFAULT_SERVING)
    missing = on_disk - published
    assert not missing, (
        f"serving models that would never be published: {sorted(missing)}")
    stale = published - on_disk
    assert not stale, (
        f"published tables with no model: {sorted(stale)}")
