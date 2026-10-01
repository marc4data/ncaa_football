"""The site must not call itself by the data provider's name.

> **MARC, 2026-09-30:** *"cfdb is the name of my VS Code project. My site and brand is
> Marc4Data, or M4D. cfdb looks/sounds like a reference to CollegeFootballData.com."*

🚨 ON A PORTFOLIO PIECE THAT IS THE WHOLE RISK. A reader meeting `cfdb` beside
`CollegeFootballData.com` most naturally parses it as the DATA PROVIDER, so the site reads as
though it belongs to the vendor. The chrome was already branded — the footer says "Built by
Marc Alexander" and the tab reads `M4D · Today` — while the body copy said `cfdb`.

## WHAT THIS CHECKS, AND THE FOUR THINGS IT DELIBERATELY DOES NOT

⚠️ **STRING LITERALS ONLY, AND NOT DOCSTRINGS.** The subject is what a READER sees. A
docstring and a comment are read by whoever opens the file, which is a different audience with
a different need — they routinely cite `cfdb-` classes, the `cfdb` database and this project's
own history, and sanitising them would cost precision for no reader-visible gain.

🚨 **AND COMMENTS ARE OUT FOR A SECOND, HARDER REASON — A267 PAID FOR IT.** Its source check
failed on its own explanatory comment, because a comment about a forbidden string necessarily
quotes it. A guard that cannot tell shipped prose from an explanation of shipped prose forbids
the documentation along with the defect. **Deciding this deliberately is the point; it is not
an oversight.**

The identifier forms are out of scope by construction, via the word boundary:

    cfdb-dist-panel     a CSS class — the theme, every render test, A262's chip rules
    cfdb_scores_*       an identifier, a fixture, a filename
    CFDB_READ_USER      an environment variable the droplet reads
    data-cfdb           an attribute render harnesses select on

⚠️ **AND THE BARE STRING `"cfdb"` IS THE DATABASE NAME**, not prose — `PG_DB`'s default in
`site/db.py` and `site/lib/query.py`. Renaming it would reach the droplet.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# `cfdb` as a WORD. A trailing apostrophe ("cfdb's own ordering") IS prose and must match.
WORD = re.compile(r"(?<![A-Za-z0-9_-])cfdb(?![A-Za-z0-9_-])", re.IGNORECASE)

# 🚨 ONE EXEMPTION, NAMED RATHER THAN SILENT (§3 — file ownership).
#
# `site/views/matchup.py` is SESSION B's file and carried 21 reader-visible instances when
# A272 swept the rest. Two sessions must not edit one file in the same week, and B's round
# takes it whole along with its display-name fix (cfdb-main-R-4406).
#
# ⚠️ THE COUNT IS PINNED, NOT WAIVED. The exemption permits exactly what was there and no
# more: a NEW instance in that file still fails this test, and the day B sweeps it the number
# drops and this entry is deleted rather than quietly left behind.
SESSION_B_FILE = "views/matchup.py"
SESSION_B_PINNED = 21

# The database name, not prose. `PG_DB`'s default; renaming it would reach the droplet.
DATABASE_NAME = "cfdb"


def _docstring_nodes(tree):
    """Every node that IS a docstring, so prose can be told from documentation."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.get_docstring(node, clean=False) is not None:
                if node.body and isinstance(node.body[0], ast.Expr):
                    out.add(id(node.body[0].value))
    return out


def reader_visible_hits(path: Path):
    """`(lineno, excerpt)` for every `cfdb` in a string a reader can see."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in skip or node.value == DATABASE_NAME:
            continue
        for match in WORD.finditer(node.value):
            start = max(0, match.start() - 50)
            found.append((node.lineno,
                          " ".join(node.value[start:match.start() + 60].split())))
    return found


def test_no_reader_visible_prose_calls_this_site_cfdb():
    offenders = []
    for path in sorted(SITE.rglob("*.py")):
        if path.relative_to(SITE).as_posix() == SESSION_B_FILE:
            continue
        for lineno, excerpt in reader_visible_hits(path):
            offenders.append(f"{path.relative_to(ROOT)}:{lineno}  …{excerpt}…")
    assert not offenders, (
        "reader-visible prose still calls this site by the data provider's name "
        "(M4D is the brand; `cfdb` is the VS Code project):\n  " + "\n  ".join(offenders))


def test_session_bs_file_is_pinned_rather_than_waived():
    """⚠️ AN EXEMPTION THAT IS NOT COUNTED IS A HOLE. This one is a number.

    `matchup.py` is session B's to sweep. Until it does, the site is inconsistent and the
    report says so — but a NEW instance there still fails, and when B sweeps it this count
    drops and the exemption goes.
    """
    found = reader_visible_hits(SITE / SESSION_B_FILE)
    assert len(found) <= SESSION_B_PINNED, (
        f"{SESSION_B_FILE} now has {len(found)} reader-visible `cfdb` instances, up from the "
        f"pinned {SESSION_B_PINNED}. Session B owns this file (§3); a new one is a regression."
        "\n  " + "\n  ".join(f"{ln}: …{ex}…" for ln, ex in found[:6]))


def test_the_footer_leads_with_the_required_meaning_and_ends_with_the_plug():
    """A272 (cfdb-main-R-4502), Marc's call: the plug returns AFTER the non-affiliation line.

    🚨 THE ORDER IS THE ASSERTION. The credit and the non-affiliation statement are what the
    provenance needs; the plug is voice. A reader who stops early has still read everything
    that matters.
    """
    import sys
    sys.path.insert(0, str(SITE))
    from lib.attribution import CFBD_CREDIT                       # noqa: PLC0415

    text = re.sub(r"<[^>]+>", "", CFBD_CREDIT)
    assert "Really cool site, check it out!" in text, "Marc asked for the plug back"
    assert text.rstrip().endswith("Really cool site, check it out!"), (
        "the plug must be the LAST sentence, after the non-affiliation line")
    assert text.index("not affiliated") < text.index("Really cool site"), (
        "the required meaning leads; the plug follows")
    assert "M4D" in text and "CollegeFootballData.com" in text
