"""🚨 A287 (cfdb-main-R-4922) — THE BLIND REASON MUST DISCRIMINATE, NOT JUST EXIST.

`deploy/cfdb_heartbeat.sh` reported `MONITOR.cannot_read_published_serving` for a MALFORMED
TIMESTAMP LITERAL on 2026-10-05, and the monitor stayed blind for four hours while published
serving answered `select 1` fine. Connection refused, authentication failed, a missing
relation, permission denied and a SQL error all collapsed into that one string, and psql's
real message went to stderr, which the watcher discards.

⚠️ A SINGLE STAGED FAILURE WOULD PROVE THE NEW STRING EXISTS, NOT THAT IT DISCRIMINATES
(the prompt's own words, and R-843's shape). So this walks the whole vocabulary and asserts
that DIFFERENT psql errors produce DIFFERENT tokens — and that the fallback still answers for
an error nobody has seen, because a reason that vanishes is worse than a vague one.
"""
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "cfdb_heartbeat.sh"


def _classifier() -> str:
    """The `serving_why` function, lifted out of the script.

    ⚠️ Lifted rather than sourced: the script runs queries at load time, so sourcing it would
    try to reach production from a unit test. Extracting also means this test FAILS if the
    function is renamed, which is the R-760 property — a guard keyed on a name that moved
    passes on nothing (R-760's sibling, R-843).
    """
    text = SCRIPT.read_text()
    m = re.search(r"^serving_why\(\) \{.*?^\}", text, re.S | re.M)
    assert m, "serving_why() is gone from deploy/cfdb_heartbeat.sh — renamed, or removed"
    return m.group(0)


def _why(stderr_text: str) -> str:
    """Run the real classifier over a canned psql stderr and return the token."""
    body = _classifier()
    script = (
        'SERVING_ERR="$(mktemp)"\n'
        f"{body}\n"
        'printf %s "$1" > "$SERVING_ERR"\n'
        'serving_why 2>/dev/null\n'
        'rm -f "$SERVING_ERR"\n'
    )
    out = subprocess.run(["bash", "-c", script, "_", stderr_text],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


# 📊 Every message below is psql's real wording. The timestamp one is VERBATIM from the
# 2026-10-05 incident, captured off the droplet by running the installed forced command and
# keeping the stderr the watcher throws away.
CASES = [
    ('ERROR:  date/time field value out of range: "2026-10-0503:50:29"', "serving_bad_literal"),
    ('psql: error: connection to server at "127.0.0.1", port 5433 failed: Connection refused',
     "serving_connection_refused"),
    ("psql: error: connection to server failed: fe_sendauth: no password supplied",
     "serving_no_password"),
    ('psql: error: connection to server at "127.0.0.1" failed: '
     'FATAL:  password authentication failed for user "cfdb_read"', "serving_auth_failed"),
    ('psql: error: FATAL:  database "nosuchdb" does not exist', "serving_database_missing"),
    ('psql: error: FATAL:  role "nosuchrole" does not exist', "serving_role_missing"),
    ('ERROR:  relation "serving.srv_game_team" does not exist', "serving_relation_missing"),
    ('ERROR:  column "has_box_advanced" does not exist', "serving_column_missing"),
    ("ERROR:  permission denied for table srv_game_team", "serving_permission_denied"),
    ("ERROR:  syntax error at or near \"slect\"", "serving_query_syntax_error"),
    ('psql: error: could not translate host name "serving" to address', "serving_host_unresolvable"),
    ("psql: error: connection failed: No route to host", "serving_host_unreachable"),
    ("ERROR:  canceling statement due to statement timeout", "serving_timeout"),
    ("psql: error: server closed the connection unexpectedly", "serving_connection_dropped"),
]


@pytest.mark.parametrize("stderr_text,expected", CASES)
def test_each_psql_error_gets_its_own_reason(stderr_text, expected):
    assert _why(stderr_text) == expected


def test_the_reasons_are_actually_DISTINCT():
    """🚨 THE POINT OF THE ROUND. Fourteen different failures must not share a token, or the
    next incident is the last one again: a reason that cannot tell two causes apart is the
    string `cannot_read_published_serving` wearing a new name."""
    tokens = [_why(s) for s, _ in CASES]
    dupes = {t for t in tokens if tokens.count(t) > 1}
    assert not dupes, f"these reasons do not discriminate: {dupes}"
    assert len(set(tokens)) == len(CASES) == 14


def test_an_unrecognised_error_still_reports_BLIND_rather_than_vanishing():
    """⚠️ The fallback is load-bearing. `ci/check_heartbeats.py` routes any `MONITOR.` value to
    BLIND; a classifier that emitted nothing for an unknown error would turn a page-class
    event into a MISSING LINE, which A185 already paid for."""
    assert _why("ERROR:  something nobody has seen before") == "cannot_read_published_serving"
    assert _why("") == "cannot_read_published_serving"


def test_the_wire_format_the_watcher_parses_is_unchanged():
    """The contract A278/A281 depend on: `<head>|MONITOR.<why>|0|-`, and the reason carries no
    `|` of its own or the watcher's split would gain a field."""
    text = SCRIPT.read_text()
    for head in ("unboxed", "unplayered", "unadvanced", "undriven", "uncurved"):
        assert f'echo "{head}|MONITOR.$(serving_why)|0|-"' in text, head
    for _stderr, token in CASES:
        assert "|" not in token and token == token.strip()


def test_the_last_fetch_clock_is_trimmed_and_not_stripped_of_every_space():
    """🚨 THE CAUSE, PINNED SO IT CANNOT COME BACK. `tr -d '[:space:]'` deleted the space
    INSIDE `YYYY-MM-DD HH24:MI:SS`, which is what took the monitor blind."""
    text = SCRIPT.read_text()
    assert "tr -d '[:space:]'" not in text, (
        "the LAST_FETCH capture is deleting every space again; it must TRIM, not DELETE")
    assert "LAST_FETCH_SHAPE=" in text, "the clock's shape is no longer asserted"
    assert "MONITOR.last_fetch_unparseable" in text, (
        "a non-empty but malformed clock must get its OWN reason, not a serving one")


def test_a_malformed_clock_is_a_different_reason_from_a_missing_one():
    """⚠️ `[ -z ]` only catches EMPTY. A280 proved the empty branch fires and that branch was
    never the problem; the value that broke production was non-empty and invalid."""
    text = SCRIPT.read_text()
    assert "MONITOR.cannot_read_last_successful_fetch" in text
    assert text.count("MONITOR.last_fetch_unparseable") >= 1
    i_empty = text.index("MONITOR.cannot_read_last_successful_fetch")
    i_bad = text.index("MONITOR.last_fetch_unparseable")
    assert i_empty < i_bad, "the empty check must still come first"
