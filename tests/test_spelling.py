"""The site speaks American English, and this is the instrument that says so.

🚨 THE SAME FINDING ARRIVED ON THREE CONSECUTIVE DAYS, ONE WORD-FAMILY AT A TIME.

  A096   the round's own near-miss — a blanket rename FLIPPED the detector to the American
         spellings, so it flagged every correct line. One word narrower and it would have
         PASSED while detecting nothing.
  R-636  the detector was never COMPLETE: it held the fragment `avourite`, so `favoured`,
         `favours` and `favourable` were invisible — all three live, all three rendered.
  R-644  `colour`, `travelled`, `centre` — seven more rendered strings, including two in the
         Excel legend Marc opens.

⚠️ **A LIST OF WORDS IS A LIST OF THE WORDS SOMEONE THOUGHT OF.** All three failures were
inflections of a stem the list already had, or a family nobody had reached yet. So this scans
by SHAPE — a stem and the endings British English puts on it — and one stem covers the whole
inflectional family rather than one word of it.

⚠️ **AND IT SCANS STRING LITERALS, NOT LINES.** That is load-bearing in both directions:

  * a line scan cannot tell `MARK_COLOURS = {` from `"The colours are"`, so it would demand a
    blanket exemption on day one — and "a guard that ships already exempted is not a guard"
    (B085). Identifiers are OURS and reach no reader; renaming them is a different round with
    its own argument.
  * a line scan also misses nothing a reader sees, which is the half people assume is fine.
    What a page ships is its string literals.

── WHAT THIS GUARD DELIBERATELY DOES NOT COVER, AND WHY (A094's rule: the limit written
   rather than discovered) ────────────────────────────────────────────────────────────────

  * SQL comments in `dbt/models/**/*.sql` — not reader-facing.
  * dbt test comments in `dbt/tests/*.sql` — not reader-facing.
  * Python docstrings and `#` comments — not shipped to a reader. (§1.1's `odds.py:9`
    docstring was fixed anyway, because the round was in the file.)
  * Everything outside `site/` in Python terms.
  * ⚠️ `tests/**`, AND THIS ONE IS LOAD-BEARING: this file's own fixtures are British by
    design. A guard that scanned `tests/` would flag itself. `test_matchup_yardage.py:455`
    also holds `"favours"` beside `"favors"` in a list it scans FOR — untouchable.
  * `docs/**` — an August snapshot, stamped as one (R-254).
  * ⚠️ `dbt/tests/assert_the_line_basis_names_the_side_that_was_favoured.sql` carries the word
    in its FILENAME. A file rename is a different class of change from editing a description;
    it is left, deliberately.
"""
import ast
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# ── THE FAMILIES ────────────────────────────────────────────────────────────────────────────
#
# 🚨 STEM × ENDING, NOT WORD. R-636's three misses — `favoured`, `favours`, `favourable` —
# were all inflections of a stem the old list already had in `avourite`. Enumerating endings
# once, for every family, is what closes that class permanently. Adding a genuinely new family
# is still an edit; adding a new *inflection* never is again.
#
# ⚠️ The stems are deliberately the longest unambiguous prefix. `fav` not `f`, so `four` and
# `hour` and `your` cannot match; `trave` not `tra`, so `traveled` (American) cannot.
_ENDINGS = ("", "s", "d", "ed", "es", "ing", "r", "rs", "ite", "ites",
            "able", "ably", "ful", "fully", "less", "ism", "ist", "ists")

FAMILIES = {
    # British keeps the `u`: colour / favour / behaviour …
    "-our": (("col", "fav", "behavi", "neighb", "hon", "flav", "lab",
              "rum", "hum", "endeav", "arm", "vap"), ("our",)),
    # British `-ence` where American writes `-ense`.
    "-ence": (("off", "def", "pret", "lic"), ("ence",)),
    # British doubles the `l` before a vowel ending.
    "-lled": (("trave", "labe", "mode", "cance", "signa", "marve", "jewe", "fue"),
              ("lled", "lling", "ller", "llers", "llery")),
    # British `-re` where American writes `-er`.
    "-re": (("cent", "met", "lit", "fib", "theat", "calib", "somb", "spect"), ("re",)),
    # British `-ogue` where American writes `-og`.
    "-ogue": (("catal", "dial", "anal", "monol", "epil", "prol"), ("ogue",)),
    # Single words with no useful stem split.
    "grey": (("gr",), ("ey",)),
    "practise": (("practi",), ("se", "sed", "ses", "sing")),
    "programme": (("programm",), ("e", "es")),
}


def _family_pattern(stems, shapes):
    stem = "|".join(sorted(stems, key=len, reverse=True))
    shape = "|".join(sorted(shapes, key=len, reverse=True))
    ending = "|".join(sorted(_ENDINGS, key=len, reverse=True))
    return re.compile(rf"\b(?:{stem})(?:{shape})(?:{ending})?\b", re.IGNORECASE)


PATTERNS = {name: _family_pattern(stems, shapes)
            for name, (stems, shapes) in FAMILIES.items()}


def british_spellings(text: str):
    """Every British spelling in `text`, as (family, matched word). The unit under test."""
    found = []
    for family, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            found.append((family, match.group(0)))
    return found


def _string_literals(tree):
    """Every string literal that is NOT a docstring, with its line number."""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


def scan_source(src: str):
    """Offenders in Python SOURCE: (line, family, word, excerpt).

    ⚠️ Takes source rather than a path so the tests can hand it three lines, which is what
    makes the identifier fixture possible — and that fixture is what pins the string-literal
    design against a future "simplification" back to a line grep.
    """
    out = []
    for lineno, value in _string_literals(ast.parse(src)):
        for family, word in british_spellings(value):
            out.append((lineno, family, word, value.strip()[:70]))
    return out


def scan_python(path: Path):
    return scan_source(path.read_text())


def site_offenders():
    out = []
    for path in sorted(SITE.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        for lineno, family, word, excerpt in scan_python(path):
            out.append(f"{path.relative_to(ROOT)}:{lineno} [{family}] {word!r} — {excerpt}")
    return out


# ── PART 2: A FUNCTIONAL TEST OF THE SCANNER ────────────────────────────────────────────────
#
# 🚨 A096 SHIPPED A MEMBERSHIP TEST AND IT WAS THE RIGHT INSTINCT AND THE WRONG ASSERTION.
# `assert ("f" + _BRITISH[0]) == "fav" + "ourite"` pins the detector to its own contents: it
# passed every single day the detector was missing three live strings, and it would fail the
# moment the list widened — for no reason except that the list changed.
#
# ⚠️ A structural assertion about a detector's contents can confirm the detector is what it
# WAS. It can never say the detector WORKS. These three do, and between them they catch both
# historical failures: the American fixture catches A096's flip, the British fixture catches
# R-636's hole.
#
# 🚨 ONE LINE PER FAMILY, NOT PER WORD. A fixture that enumerated words would reproduce the
# exact failure it exists to catch — it would have been green on all three days.

BRITISH_FIXTURE = {
    "-our": "The colours are the direction, not a judgement.",
    "-our/inflected": "the home team was favoured, and the book favours it still",
    "-ence": "Offence and defence, one apiece.",
    "-lled": "how far the number has travelled since it opened",
    "-re": "drawn as a bar from a centre line",
    "grey": "the same grey disc a null gives",
    "-ogue": "a catalogue of every column",
    "programme": "the modelling programme",
    "case": "COLOUR, Favoured, DEFENCE",
}

AMERICAN_FIXTURE = (
    "The colors are the direction, not a judgment.",
    "the home team was favored, and the book favors it still",
    "Offense and defense, one apiece.",
    "how far the number has traveled since it opened",
    "drawn as a bar from a center line",
    "the same gray disc a null gives",
    "a catalog of every column",
    "the modeling program",
    "COLOR, Favored, DEFENSE",
    # ⚠️ Words that merely LOOK like the families and must never be flagged.
    "an hour later, four of them, on tour, pour it out, your call",
    "the literal centerpiece of the meter reading",
    "he called, filled, spelled and killed it",
)

IDENTIFIER_FIXTURE = """
MARK_COLOURS = {}
COLOUR_SCALE_FIELDS = ()
text_colour = x
sheet.centred = True
ALWAYS_CENTRED_LABELS = []
value = row.centred_fields
"""


@pytest.mark.parametrize("family", sorted(BRITISH_FIXTURE))
def test_every_british_family_is_detected(family):
    """🚨 R-636's HOLE. One line per family; every one must be flagged.

    Delete a family's rule and this goes red — which is the break that matters, because no
    test in the repo before this one would have caught it.
    """
    line = BRITISH_FIXTURE[family]
    assert british_spellings(line), (
        f"the {family} family is not detected: {line!r}. A spelling the guard cannot see is "
        f"a spelling that ships — R-636 was three of them, all live and all rendered.")


@pytest.mark.parametrize("line", AMERICAN_FIXTURE)
def test_no_american_spelling_is_flagged(line):
    """🚨 A096's FLIP. The rename rewrote the detector into the American spellings, so it
    flagged every correct line and failed for the opposite of its reason.

    ⚠️ The last three lines are the near-misses: `hour`, `four`, `tour`, `literal`, `meter`,
    `called`, `filled`. A stem that was one letter shorter would match them.
    """
    assert not british_spellings(line), (
        f"an American spelling was flagged: {line!r} -> {british_spellings(line)}. The "
        f"detector has been inverted, or a stem is too short.")


def test_identifiers_are_never_flagged():
    """🚨 THIS IS THE TEST THAT PINS §1.2, AND IT IS THE ONE A CARELESS ROUND WOULD DROP.

    `MARK_COLOURS`, `text_colour`, `sheet.centred` are OURS. They reach no reader, and
    renaming them is a different round with its own argument. A line-based scan cannot tell
    `MARK_COLOURS = {` from `"The colours are"` — so without this fixture, the next round that
    "simplifies" the scanner back to a grep passes its own tests and demands a blanket
    exemption on day one. "A guard that ships already exempted is not a guard" (B085).
    """
    assert scan_source(IDENTIFIER_FIXTURE) == [], (
        f"an identifier was flagged: {scan_source(IDENTIFIER_FIXTURE)}. The scanner is reading "
        f"lines rather than string literals.")


def test_a_string_literal_beside_an_identifier_is_still_caught():
    """⚠️ AND THE OTHER DIRECTION, so the test above cannot be satisfied by a scanner that
    has simply stopped working."""
    found = scan_source('MARK_COLOURS = {"legend": "The colours are the direction"}\n')
    assert found, "a British spelling inside a literal was missed"
    assert any(word == "colours" for _ln, _fam, word, _x in found)


# ── THE TWO TREE SCANS ──────────────────────────────────────────────────────────────────────

# ONE exemption, spelled out rather than pattern-matched. `CSV_LABEL_OVERRIDES`'s KEY is the
# header in Marc's column-order CSV, quoted verbatim; the VALUE is the American label the sheet
# ships. Rewriting the key would make a recorded divergence look like a typo.
EXEMPT_LITERALS = {"Favourite covered"}


def test_no_user_facing_string_uses_british_spelling():
    """Marc: "Use US version of favorite." Every string literal the site ships."""
    offenders = []
    for path in sorted(SITE.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        for lineno, family, word, excerpt in scan_python(path):
            if excerpt in EXEMPT_LITERALS:
                continue
            offenders.append(
                f"{path.relative_to(ROOT)}:{lineno} [{family}] {word!r} — {excerpt}")
    assert not offenders, offenders


def _descriptions(node):
    """Every `description` value in a parsed dbt schema file."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                yield value
            else:
                yield from _descriptions(value)
    elif isinstance(node, list):
        for value in node:
            yield from _descriptions(value)


def _json_strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _json_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _json_strings(value)
    elif isinstance(node, str):
        yield node


def test_no_dbt_description_uses_british_spelling():
    """🚨 R-638. THE DICTIONARY SPELLED IT `favourite` IN THE DEFINITION OF `favorite_covered`.

    The column name and its own definition disagreed about the spelling, on the same row of
    the page Marc reads.

    ⚠️ ALL THREE MODELLED LAYERS ARE READER-FACING, and this was checked rather than assumed:
    `dim_field_metadata.sql` catalogs serving, dimensional and staging (raw deliberately
    excluded); `views/dictionary.py`'s LAYERS selectbox offers all three; and `persist_docs`
    is set at the PROJECT level in dbt_project.yml, not per layer. A marts or staging
    description is one selectbox away from a reader.

    🚨 IT PARSES, IT DOES NOT GREP. A line grep cannot tell a description from a YAML comment,
    and a comment is not reader-facing — A094's first `check_page_reads.py` missed B084's
    defect for exactly this reason.
    """
    offenders = []
    for path in sorted(ROOT.glob("dbt/models/**/_models*.yml")):
        document = yaml.safe_load(path.read_text())
        for text in _descriptions(document):
            for family, word in british_spellings(text):
                offenders.append(f"{path.relative_to(ROOT)} [{family}] {word!r} — {text[:70]}")

    dictionary = ROOT / "src" / "data_dictionary" / "definitions.json"
    for text in _json_strings(json.loads(dictionary.read_text())):
        for family, word in british_spellings(text):
            offenders.append(f"{dictionary.relative_to(ROOT)} [{family}] {word!r} — {text[:70]}")

    assert not offenders, offenders
