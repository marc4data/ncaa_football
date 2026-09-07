"""A description line ending in a hyphen is always a bug, and only the rendered page shows it.

WHAT THIS CATCHES, AND HOW IT GOT HERE. YAML's folded block scalar (`description: >`) joins
its wrapped lines WITH A SPACE. So a description whose line break lands mid-hyphenated-word:

    description: >
      URL-safe identifier, name AND player id. The id is load-bearing: 1,343 name-and-
      season combinations map to more than one athlete.

publishes as "1,343 name-and- season combinations" — a broken word with a gap in it, pushed
into the database by persist_docs and read straight back out by srv_data_dictionary onto the
site's Data Dictionary page.

TWO OF THESE SURVIVED EVERY REVIEW THIS PROJECT HAS, including the session that wrote one of
them. They are invisible in the diff, invisible in the YAML, invisible in `dbt parse`, and
legible only on the rendered page — which is the shape that belongs in a test rather than in
a checklist. They were found by accident, by an assertion written for something else.

THERE IS NO LEGITIMATE INSTANCE. Wrapping is the author's choice and every hyphenated word
can be moved whole onto the next line, so this needs no allowlist. The fix is mechanical:
rewrap, do not delete the hyphen and do not reword — these are published strings.

LITERAL BLOCKS (`|`) ARE CHECKED TOO, on a weaker but real argument: a literal scalar keeps
the newline rather than turning it into a space, so nothing is joined — but the word is still
split across lines, and every renderer that reflows text (markdown, HTML, the Excel export's
cell wrap) puts it back together wrongly. The repo uses `>` almost exclusively; including `|`
costs nothing and closes the variant before somebody writes it.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODELS = REPO / "dbt" / "models"

# A key introducing a block scalar: `description: >`, `> -`, `|+`, with an optional comment.
_BLOCK_START = re.compile(r"^(?P<indent>\s*)(?:- )?[\w.\"']+\s*:\s*(?P<style>[>|])[-+]?\s*(?:#.*)?$")
# The bug: a line whose last character is a hyphen preceded by a word character.
_TRAILING_HYPHEN = re.compile(r"\w-$")


def _offences(path: Path):
    """Every (line_number, text) inside a block scalar that ends in a word-char + hyphen."""
    out = []
    block_indent = None
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.rstrip("\n")
        if block_indent is not None:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if stripped and indent <= block_indent:
                block_indent = None          # dedented out of the block
            elif stripped and _TRAILING_HYPHEN.search(stripped):
                out.append((number, stripped))
                continue
        if block_indent is None:
            match = _BLOCK_START.match(line)
            if match:
                block_indent = len(match.group("indent"))
    return out


def _yaml_files():
    return sorted(MODELS.rglob("*.yml")) + sorted(MODELS.rglob("*.yaml"))


def test_there_are_yaml_files_to_check():
    """A guard that silently checks nothing is worse than no guard."""
    files = _yaml_files()
    assert len(files) >= 3, f"expected the model yaml files, found {files}"


@pytest.mark.parametrize("path", _yaml_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_block_scalar_line_ends_in_a_hyphen(path):
    found = _offences(path)
    assert not found, (
        "folded/literal block scalar lines ending in a hyphen — these publish as a broken "
        "word with a gap in it. Rewrap so the hyphenated word sits whole on one line; do not "
        "delete the hyphen and do not reword (these strings are published):\n"
        + "\n".join(f"  {path.relative_to(REPO)}:{n}: {t}" for n, t in found)
    )
