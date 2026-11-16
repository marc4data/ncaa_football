"""Every singular assertion in dbt/tests/ says, in its own file, whether it may stop a publish.

A294 (cfdb-main-R-5132).

📊 WHY: until A294, 84 of the 142 singular tests carried no `config()` at all, so their severity
was dbt's default `error` rather than anyone's decision — and because `publish_to_serving` runs
only when `dbt_test` succeeds, 129 of them could each hold the whole site off the air on one row.
A294 made `warn` the project default (dbt_project.yml, `data_tests:`) and gave every test an
explicit severity. This check keeps it that way: a test that does not say which it is has not
been thought about, whichever way the default would have resolved it.

⚠️ IT DECLARES, IT DOES NOT SILENCE. `severity='error'` passes exactly as `severity='warn'` does.

🚨 COMMENTS ARE STRIPPED BEFORE MATCHING. This project's tests document themselves densely, and
several headers discuss `config(severity=...)` in prose (CLAUDE.md §2.2.1c.1: the prose about a
symbol outnumbers the code using it). A test whose only `severity=` is inside a `--` comment or a
`{# #}` block declares nothing, and this check says so.

Usage:  python ci/check_test_severity_declared.py [tests_dir]      exit 1 on any undeclared test
"""
import re
import sys
from pathlib import Path

TESTS_DIR = Path("dbt/tests")
# Generic test DEFINITIONS (macros), not assertions; their instances are configured in YAML.
GENERIC_DIR = "generic"

_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)
_SQL_COMMENT = re.compile(r"--[^\n]*")
_CONFIG = re.compile(r"\{\{\s*config\((.*?)\)\s*\}\}", re.S)
_SEVERITY = re.compile(r"""\bseverity\s*=\s*['"](warn|error)['"]""", re.I)


def declared_severity(sql: str):
    """The severity a test's own `config()` states, or None if it states none."""
    code = _SQL_COMMENT.sub("", _JINJA_COMMENT.sub("", sql))
    for call in _CONFIG.finditer(code):
        found = _SEVERITY.search(call.group(1))
        if found:
            return found.group(1).lower()
    return None


def undeclared(tests_dir: Path = TESTS_DIR):
    """Paths of singular tests under `tests_dir` that do not declare a severity."""
    missing = []
    for path in sorted(tests_dir.rglob("*.sql")):
        if GENERIC_DIR in path.relative_to(tests_dir).parts[:-1]:
            continue
        if declared_severity(path.read_text()) is None:
            missing.append(path)
    return missing


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tests_dir = Path(argv[0]) if argv else TESTS_DIR
    missing = undeclared(tests_dir)
    if not missing:
        print(f"every singular test under {tests_dir} declares its severity")
        return 0
    for path in missing:
        print(f"::error file={path}::{path.name} does not declare its severity. Add "
              f"{{{{ config(severity='warn') }}}} — or 'error' ONLY if a failure means the site "
              f"would show something factually wrong that a reader would act on (A294).")
    print(f"{len(missing)} singular test(s) without a declared severity")
    return 1


if __name__ == "__main__":
    sys.exit(main())
