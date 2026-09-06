"""Every name a module imports from another project module must actually exist there.

WHY THIS EXISTS (R-395). On 2026-09-06 `main` shipped this, and the suite was green:

    # src/export_sample.py, inside export()
    from .load_raw_to_postgres import PG_HOST, PG_PORT, get_conn

`env/droplet-only` had removed PG_HOST and PG_PORT from that module hours earlier, replacing
them with pg_params(). The import sits INSIDE A FUNCTION BODY, so importing the module
succeeds and nothing raises until export() is actually called — which no test does. Marc's
staging-export runbook was broken and the only thing that would have told him was running it.

THE CLASS, NOT THE LINE. A test that imported export_sample, or that called export(), would
have caught this one instance and nothing else. The general fault is "a module imports a name
from a sibling that no longer defines it, on a path the tests never execute." That is
answerable statically for the whole repo, without importing anything and without a database:
parse every file, resolve every intra-project `from X import a, b`, and check the names are
defined in the target.

DELIBERATELY STATIC. Importing modules to check them would need streamlit, Airflow and a live
connection, which is exactly why the untested paths are untested.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("src", "dags", "ci", "scripts", "site", "tests")


def _module_path(module: str, relative_to: Path, level: int) -> Path | None:
    """Resolve a dotted module name to a file in this repo, or None if it is third-party."""
    if level:                                   # relative: from .x import y
        base = relative_to.parent
        for _ in range(level - 1):
            base = base.parent
        candidate = base.joinpath(*module.split(".")) if module else base
    else:                                       # absolute: from src.x import y
        candidate = ROOT.joinpath(*module.split("."))
    for path in (candidate.with_suffix(".py"), candidate / "__init__.py"):
        if path.is_file():
            return path
    return None


def _defined_names(path: Path) -> set[str]:
    """Names a module binds at module level, including inside try/except and if blocks.

    Anything bound conditionally still counts — the point is to catch a name that exists
    NOWHERE, not to reason about which branch runs.
    """
    names: set[str] = set()

    def walk(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
            elif isinstance(node, (ast.If, ast.Try)):
                walk(node.body)
                walk(getattr(node, "orelse", []))
                walk(getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    walk(handler.body)
    walk(ast.parse(path.read_text(encoding="utf-8")).body)
    return names


def _sources():
    for package in PACKAGES:
        directory = ROOT / package
        if directory.is_dir():
            yield from sorted(p for p in directory.rglob("*.py")
                              if "__pycache__" not in p.parts and ".venv" not in p.parts)


def test_every_intra_project_import_resolves():
    scanned, checked, broken = 0, 0, []
    for path in _sources():
        scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:                                   # noqa: PERF203
            broken.append(f"{path.relative_to(ROOT)}: will not parse — {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _module_path(node.module or "", path, node.level or 0)
            if target is None or target == path:
                continue                     # third-party, stdlib, or self
            available = _defined_names(target)
            # A PACKAGE IMPORT MAY NAME A SUBMODULE, NOT A BINDING. `from src.data_dictionary
            # import definitions` resolves to definitions.py and never touches __init__.py's
            # namespace — the first draft of this check called all three such imports broken,
            # which is the false positive that makes a guard get deleted rather than fixed.
            if target.name == "__init__.py":
                available |= {p.stem for p in target.parent.glob("*.py")}
                available |= {p.name for p in target.parent.iterdir() if (p / "__init__.py").is_file()}
            for alias in node.names:
                if alias.name == "*":
                    continue
                checked += 1
                if alias.name not in available:
                    broken.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} imports "
                        f"`{alias.name}` from {target.relative_to(ROOT)}, "
                        f"which does not define it")

    # AN EMPTY SCAN IS THE FAILURE THIS FILE EXISTS TO PREVENT REPEATING (R-338).
    assert scanned > 50, f"only scanned {scanned} files — the globs are wrong, not the code"
    assert checked > 50, f"only resolved {checked} imports — the resolver is wrong, not the code"
    assert not broken, "unresolvable intra-project imports:\n  " + "\n  ".join(broken)


@pytest.mark.parametrize("name", ["get_conn", "pg_params"])
def test_the_loader_still_exports_what_export_sample_needs(name):
    """The specific regression, pinned. R-395.

    Narrow on purpose and NOT a substitute for the check above — this pins the one line that
    broke, that one names the class.
    """
    assert name in _defined_names(ROOT / "src" / "load_raw_to_postgres.py")
