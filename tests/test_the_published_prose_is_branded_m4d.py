"""The WAREHOUSE's prose must not call this project by the data provider's name either.

A274 · cfdb-main-R-4532.

> **MARC, 2026-09-30:** *"cfdb is the name of my VS Code project. My site and brand is
> Marc4Data, or M4D. cfdb looks/sounds like a reference to CollegeFootballData.com."*

🚨 A272 SWEPT `site/` AND THE RENDER STILL SHOWED `cfdb`, BECAUSE THE STRING LIVED IN dbt.
A272's counter and Cowork's earlier grep both scanned `site/` only — R-859's class, twice, by two
instruments. This guard is the other half, and it is a SEPARATE FILE from
`test_the_site_is_branded_m4d.py` on purpose: that one is session B's this week (§3), and two
sessions editing one file in one week is what §3 exists to prevent.

## WHY A dbt DESCRIPTION IS READER-VISIBLE AT ALL

`persist_docs: {relation: true, columns: true}` is set at the PROJECT level in
`dbt/dbt_project.yml`, so every `description:` in every layer is written into the database as a
native comment, read back out by `dim_field_metadata`, and rendered on the **Data Dictionary**
page and in the workbook's Data Dictionary sheet. 📊 A274 counted **27** of them.

⚠️ AND THEY NEED `scripts/deploy_main.sh --rebuild` TO REACH THE READER (§3.5):
`state:modified+` does not select a model whose only change is its description, so an ordinary
deploy ships the YAML, builds nothing, publishes nothing — and reports success.

## WHAT IS EXCLUDED, AND WHY — STRUCTURALLY, NOT BY A REGEX

⚠️ **YAML COMMENTS ARE NOT SCANNABLE BY CONSTRUCTION.** `yaml.safe_load` returns the
document, and a comment is not in it. A comment is read by whoever opens the file — a different
audience — and a comment *about* a forbidden string necessarily quotes it. **A267 paid for that:
its source check failed on its own explanatory comment.** The same ruling A272 made for Python
docstrings.

⚠️ **SQL COMMENTS** are stripped before the literal scan; 22 of them legitimately discuss this
project's own history.

❌ **`dbt/profiles*/profiles.yml` IS THE DATABASE NAME and is never opened** — this guard globs
`dbt/models/**` only, and renaming it would reach the droplet.

❌ **EVERY IDENTIFIER FORM is out of scope via the word boundary** — `cfdb_scores_refresh`,
`cfdb-pipeline`, `CFDB_READ_USER`, `data-cfdb`. They reach the droplet.

❌ **DOUBLE-QUOTED SQL SPANS** are not scanned: in SQL a double quote is an IDENTIFIER quote,
not a string, so such a span is not prose.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "dbt" / "models"

# `cfdb` as a WORD. A trailing apostrophe ("cfdb's own telemetry") IS prose and must match.
WORD = re.compile(r"(?<![A-Za-z0-9_-])cfdb(?![A-Za-z0-9_-])", re.IGNORECASE)

# A single-quoted SQL literal, `''` escape included. This is the form that reaches a reader —
# `srv_game_team.sql`'s attribution column is one, and it was the only one in the project.
SQL_LITERAL = re.compile(r"'(?:[^']|'')*'")

# Floors, so a guard keyed on a path that moved cannot pass by opening nothing (R-760).
MIN_YAML_FILES = 8
MIN_SQL_FILES = 150


def _descriptions(node, trail=""):
    """Every `description:` value in a parsed dbt YAML document, with where it came from."""
    if isinstance(node, dict):
        for key, value in node.items():
            name = node.get("name") if isinstance(node.get("name"), str) else None
            if key == "description" and isinstance(value, str):
                yield (f"{trail}.{name}" if name else trail or "<root>"), value
            else:
                yield from _descriptions(value, f"{trail}.{key}")
    elif isinstance(node, list):
        for item in node:
            yield from _descriptions(item, trail)


def _strip_sql_comments(text: str) -> str:
    """`/* */` and `--` removed, so a comment discussing the brand is not mistaken for prose."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


def _excerpt(value: str, at: int) -> str:
    return " ".join(value[max(0, at - 55):at + 60].split())


def description_offenders():
    """`(file, path, excerpt)` for every `cfdb` in prose the warehouse publishes."""
    offenders, opened = [], 0
    for path in sorted(MODELS.rglob("*.yml")):
        opened += 1
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for where, value in _descriptions(document):
            for match in WORD.finditer(value):
                offenders.append(
                    (path.relative_to(ROOT).as_posix(), where, _excerpt(value, match.start())))
    return offenders, opened


def sql_literal_offenders():
    """`(file, lineno, literal)` for every `cfdb` in a SQL string a reader can see."""
    offenders, opened = [], 0
    for path in sorted(MODELS.rglob("*.sql")):
        opened += 1
        body = _strip_sql_comments(path.read_text(encoding="utf-8"))
        for match in SQL_LITERAL.finditer(body):
            if WORD.search(match.group(0)):
                lineno = body[:match.start()].count("\n") + 1
                offenders.append(
                    (path.relative_to(ROOT).as_posix(), lineno, match.group(0)[:120]))
    return offenders, opened


def test_no_published_description_calls_this_project_cfdb():
    offenders, _ = description_offenders()
    assert not offenders, (
        "a dbt description still calls this project by the data provider's name — these are "
        "persisted as database comments and rendered on the Data Dictionary page and in the "
        "workbook (M4D is the brand; `cfdb` is the VS Code project):\n  "
        + "\n  ".join(f"{f}  {w}\n      …{e}…" for f, w, e in offenders))


def test_no_published_sql_string_literal_calls_this_project_cfdb():
    offenders, _ = sql_literal_offenders()
    assert not offenders, (
        "a SQL string literal under dbt/models still says `cfdb`. A literal is published "
        "data, not a comment — `srv_game_team`'s attribution column was one:\n  "
        + "\n  ".join(f"{f}:{n}  {lit}" for f, n, lit in offenders))


def test_this_guard_actually_opened_the_files_it_claims_to_check():
    """🚨 R-760: a guard keyed on a path that does not exist passes on zero files.

    Both halves above are satisfied by an empty iteration, and an empty iteration is exactly
    what a renamed directory produces. So the file counts are asserted, not assumed.
    """
    _, yaml_files = description_offenders()
    _, sql_files = sql_literal_offenders()
    assert yaml_files >= MIN_YAML_FILES, (
        f"only {yaml_files} YAML files under {MODELS} — this guard is checking nothing")
    assert sql_files >= MIN_SQL_FILES, (
        f"only {sql_files} SQL files under {MODELS} — this guard is checking nothing")


def test_the_exclusions_are_exercised_rather_than_merely_stated():
    """⚠️ AN EXCLUSION NOTHING EXERCISES IS AN EXCLUSION THAT MIGHT NOT WORK.

    The identifier forms and the SQL comments are the reason this guard can be green at all.
    If the word boundary or the comment stripper broke, these would start matching and the
    two tests above would fail for the wrong reason — so each is pinned by a live example.
    """
    assert not WORD.search("cfdb_scores_refresh and cfdb-pipeline and CFDB_READ_USER")
    assert not WORD.search("data-cfdb-anchor")
    assert WORD.search("M4D was cfdb's name"), "a possessive IS prose and must match"

    # A real SQL comment discussing this project, from `srv_system_health.sql`. The stripper
    # must remove it; if it ever stops, that test goes red on documentation.
    comment = "-- Postgres-only. This model's source is cfdb's own telemetry\nselect 1\n"
    assert not WORD.search(_strip_sql_comments(comment))

    # And the YAML side's exclusion is structural: a comment is not in the parsed document.
    parsed = yaml.safe_load("# cfdb's own telemetry\nmodels:\n  - name: x\n    description: ok\n")
    assert [v for _, v in _descriptions(parsed)] == ["ok"]
