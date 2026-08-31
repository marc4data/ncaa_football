"""The CI fixture has to be valid before it can test anything.

A malformed JSON literal in ci/fixtures.sql fails the dbt job with a Postgres parse error
several steps removed from the cause, and it reads like a broken model. This turned up while
adding the stats family: a template produced `177,,` and, once that was fixed, a missing comma
after a nested object — two errors that cost a round trip to the droplet each to discover.

Parsing them here costs milliseconds and names the offending literal.
"""
import json
import re
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "ci" / "fixtures.sql"

# Single-quoted SQL string literals that look like a JSON object. The fixture never embeds an
# apostrophe inside one, which is what makes this simple pattern safe here.
JSON_LITERAL = re.compile(r"'(\{.*?\})'", re.S)


def literals():
    return [m.group(1) for m in JSON_LITERAL.finditer(FIXTURES.read_text())]


def test_the_fixture_has_json_payloads_to_check():
    """Guard against the pattern silently matching nothing and the test passing vacuously —
    which would be its own version of the bug it exists to catch."""
    assert len(literals()) > 20


def test_every_json_literal_in_the_fixture_parses():
    broken = []
    for literal in literals():
        try:
            json.loads(literal)
        except json.JSONDecodeError as error:
            head = " ".join(literal[:120].split())
            broken.append(f"{error} — near: {head}")
    assert not broken, "invalid JSON in ci/fixtures.sql:\n" + "\n".join(broken)


def test_every_landed_payload_declares_its_status():
    """Each fixture row mirrors a real landed response, and staging models filter on
    `status_code = 200` before touching the payload. A literal without one is a row no model
    would ever read, which makes it a fixture that tests nothing."""
    missing = [" ".join(lit[:90].split()) for lit in literals()
               if "status_code" not in lit and '"data"' in lit]
    assert not missing, missing
