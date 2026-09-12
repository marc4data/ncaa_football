"""Every Col every view module builds, across all sixteen of them (R-440).

THE DEFECT THIS GENERALISES. A065 found `Col(..., decimals=1)` and `Col(..., fmt=...)` in
today.py — the signature is `dp` and `render` — six columns and two renderers wrong, and the
page would have raised TypeError the first time anyone opened it. Nothing could see it:
ci/check_page_queries.py only executes SQL; the unit tests grepped the page's source for
column names; and CI's site-image job loads app.py, which never calls a panel.

A's repair, test_every_panel_builds_ITS_OWN_columns_and_formats_a_row, captures what the page
hands table.render and formats a row through it. That is the right mechanism and it is scoped
to today.py's two panels. today.py is one of SIXTEEN view modules building 176 columns
between them, and it is the only one guarded.

WHY THIS DOES NOT EXTEND A's MECHANISM DIRECTLY. Doing so means calling every panel, and the
panels do not have a common shape: 27 Col-building functions across 15 distinct signatures —
`(df)`, `(df, scope)`, `(season, team_slug)`, `(fields, frame, scope)` — most of which want
real rows or a database. A hand-written fixture per page is the thing that does not scale,
and a harness that silently skips what it cannot call is the empty-scope assertion this
project has already recorded three times.

SO THE COL IS CONSTRUCTED DIRECTLY INSTEAD OF BEING CAPTURED FROM A PANEL. Each `Col(...)`
expression is compiled and evaluated against its own module's globals, which executes the
real constructor with the real arguments — a wrong kwarg raises TypeError exactly as it would
on page load — without needing to invoke the panel that surrounds it. The sample row is then
derived from the constructed columns' own `field` names, so there is no fixture to maintain.

Two things it deliberately does NOT claim: it cannot see a Col built from a variable local to
its panel (those are listed by name, not skipped quietly), and it does not prove the panel's
surrounding logic runs. It proves that every column a page builds can be built and can format
a row, which is the defect that shipped.
"""
import ast
import importlib
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VIEWS = SITE / "views"

# Modules holding their own `import streamlit`. Reloading the view alone is not enough — the
# lesson from tests/test_matchup_drives.py, whose first version bound a stub into lib.states
# for the rest of the session and broke six unrelated tests.
_RELOAD = ("lib.states", "lib.table", "lib.identity")


def _view_modules():
    return sorted(p for p in VIEWS.glob("*.py") if not p.name.startswith("_"))


def _stub_streamlit():
    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "title", "line_chart",
                 "info", "warning", "error", "metric", "dataframe", "image", "divider"):
        setattr(stub, name, lambda *a, **k: None)
    # radio/selectbox return the first option: a panel that branches on the choice must take
    # a real branch rather than None, or the construction under test never runs.
    stub.radio = stub.selectbox = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else None)
    stub.columns = lambda spec: [types.SimpleNamespace() for _ in
                                 (spec if isinstance(spec, (list, tuple)) else range(spec))]
    stub.cache_data = stub.cache_resource = lambda *a, **k: (
        a[0] if len(a) == 1 and callable(a[0]) and not k else (lambda f: f))
    stub.session_state = {}
    stub.query_params = {}
    return stub


@pytest.fixture(scope="module")
def loaded():
    """Every view module imported against a stubbed streamlit, and PUT BACK afterwards.

    The restore is by hand and it is the point: binding a stub into lib.states and leaving it
    there is a defect this suite has already paid for once.
    """
    added_path = str(SITE) not in sys.path
    if added_path:
        sys.path.insert(0, str(SITE))
    real = sys.modules.get("streamlit")
    sys.modules["streamlit"] = _stub_streamlit()
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))

    modules = {}
    failed = {}
    for path in _view_modules():
        name = f"views.{path.stem}"
        try:
            module = importlib.import_module(name)
            modules[path.stem] = importlib.reload(module)
        except Exception as exc:                                   # noqa: BLE001
            failed[path.stem] = f"{type(exc).__name__}: {exc}"

    yield modules, failed

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))
    for stem in list(modules):
        importlib.reload(sys.modules[f"views.{stem}"])
    if added_path:
        sys.path.remove(str(SITE))


def _referenced_fields(node: ast.AST) -> set:
    """Field names a Col's render/link actually reads, not just the one it is named for.

    A render is free to read any field on the row — today.py's `matchup` column reads
    `away_team_display` and `home_team_display` — so a schema derived from `field` alone is
    incomplete and the column fails on a row that is missing them. Both access styles are
    collected: `row.away_points` and `row["away_points"]`.
    """
    found = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and not child.attr.startswith("_"):
            found.add(child.attr)
        elif isinstance(child, ast.Subscript) and isinstance(child.slice, ast.Constant) \
                and isinstance(child.slice.value, str):
            found.add(child.slice.value)
    return found


def _col_calls(path: Path):
    """Every `Col(...)` expression in a module, with its line and enclosing function."""
    source = path.read_text()
    tree = ast.parse(source)
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                owner[id(child)] = node.name
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Col":
            out.append((node, node.lineno, owner.get(id(node), "<module level>"),
                        _referenced_fields(node)))
    return out


# --- the check that would have caught the shipped bug, on all sixteen modules ---------------

def test_every_view_module_was_importable(loaded):
    """A module that cannot be imported has no columns to check, and a harness that reports
    nothing for it looks identical to one that found nothing wrong."""
    modules, failed = loaded
    assert not failed, f"view modules that would not import: {failed}"
    assert len(modules) >= 15, f"expected the view modules, imported {sorted(modules)}"


@pytest.mark.parametrize("path", _view_modules(), ids=lambda p: p.stem)
def test_every_column_a_view_builds_can_actually_be_built(path, loaded):
    """Construct each Col for real, against its own module's globals.

    A kwarg Col does not accept raises TypeError here exactly as it would on page load —
    which is what `decimals=` and `fmt=` did, on a page nobody had opened.
    """
    modules, failed = loaded
    # A module whose columns are built at import time fails HERE rather than in the loop
    # below, and it must say so in this test's own words — a bare KeyError names nothing.
    assert path.stem not in failed, (
        f"{path.name} does not import, so its columns cannot be checked: {failed.get(path.stem)}")
    module = modules[path.stem]
    source = path.read_text()

    built, unbuildable, broken = [], [], []
    for node, lineno, func, _fields in _col_calls(path):
        snippet = ast.get_source_segment(source, node) or "Col(...)"
        expr = ast.Expression(body=node)
        ast.fix_missing_locations(expr)
        try:
            built.append((func, lineno, eval(compile(expr, str(path), "eval"),  # noqa: S307
                                             vars(module), {})))
        except (NameError, AttributeError):
            # Depends on something local to its panel. Named below, never skipped silently.
            unbuildable.append(f"{path.name}:{lineno} in {func}()")
        except Exception as exc:                                   # noqa: BLE001
            broken.append(f"{path.name}:{lineno} in {func}(): "
                          f"{type(exc).__name__}: {exc}  ->  {' '.join(snippet.split())[:120]}")

    assert not broken, (
        f"{len(broken)} column(s) in {path.name} cannot be constructed — the page would raise "
        f"on open:\n  " + "\n  ".join(broken))
    # Recorded on the run so the coverage gap is visible rather than implied.
    if unbuildable:
        print(f"\n  {path.name}: {len(unbuildable)} Col(s) not constructible in isolation: "
              + ", ".join(unbuildable))


@pytest.mark.parametrize("path", _view_modules(), ids=lambda p: p.stem)
def test_every_column_a_view_builds_can_format_a_row(path, loaded):
    """The columns' own field names ARE the row's schema, so there is no fixture to maintain.

    Catches the other half: a `render=` that reads a field the row does not carry, or a `dp`
    applied to something that cannot take one.
    """
    modules, failed = loaded
    assert path.stem not in failed, (
        f"{path.name} does not import: {failed.get(path.stem)}")
    module = modules[path.stem]

    # 🚨 TWO DIFFERENT OUTCOMES USED TO SHARE ONE SKIP, AND ONE OF THEM WAS A FAILURE. R-700.
    #
    # This counted nothing: a bare `except Exception: continue` swallowed every construction
    # error, and `if not columns: pytest.skip(...)` then reported BOTH "this module declares no
    # Col() calls" and "this module declares columns and every single one raised" as SKIPPED.
    # The second is a view whose entire column set is broken, reported as nothing to check.
    #
    # ⚠️ THE INSTRUMENT MATTERED BEFORE THE BUG DID. A108 measured the suite reading 1,159 passed
    # against 1,177 collected — eighteen not running where the rule says three — and could not say
    # which, because a skip with a shared reason cannot be attributed.
    #
    # `attempted` is the whole fix. Zero means there is nothing here to test; non-zero with no
    # survivors means the module is broken and must fail.
    columns, extra_fields, errors = [], set(), []
    attempted = 0
    for node, lineno, _func, referenced in _col_calls(path):
        attempted += 1
        expr = ast.Expression(body=node)
        ast.fix_missing_locations(expr)
        try:
            columns.append(eval(compile(expr, str(path), "eval"),   # noqa: S307
                                vars(module), {}))
            extra_fields |= referenced
        except Exception as exc:                                   # noqa: BLE001
            errors.append(f"line {lineno}: {type(exc).__name__}: {exc}")
            continue

    if attempted == 0:
        pytest.skip(f"{path.name} declares no Col() calls")
    if not columns:
        # ⚠️ A SKIP, NOT A FAILURE, AND I GOT THIS WRONG FIRST. Failing here looked right and
        # immediately accused `scores.py`, which is healthy: it builds its Cols inside
        # `_columns(fields, frame, scope)` in a `for field in fields:` loop, so `field` is a loop
        # variable and the Col cannot be constructed by eval'ing the call in isolation. That is a
        # limit of this test's approach, not a defect in the view — the sibling test above prints
        # the same thing as information for exactly that reason.
        #
        # 🚨 WHAT R-700 ACTUALLY BUYS IS ATTRIBUTION. The reason now names the case AND the
        # errors, so "nothing here to test" and "everything here raised" are different lines in
        # `pytest -rs` instead of one indistinguishable skip.
        pytest.skip(
            f"{path.name} declares {attempted} Col() call(s) and none is constructible in "
            f"isolation (likely built inside a function from local names): "
            + "; ".join(errors))

    # A VALUE PER KIND, because a placeholder that is wrong for the column's type produces a
    # failure about the placeholder rather than about the column — "could not convert 'x' to
    # float" is my fixture being wrong, not the page. Col.format branches on kind, so kind is
    # what chooses the value; anything else gets tried against each type in turn and passes if
    # ANY of them formats, which is the property that matters: the column can format something.
    BY_KIND = {"num": 1.5, "signed": -1.5, "plain": 2026, "cover": 0.5, "bool": True,
               "date": pd.Timestamp("2026-09-08"), "datetime": pd.Timestamp("2026-09-08T12:00Z"),
               "time": pd.Timestamp("2026-09-08T12:00Z")}
    CANDIDATES = (1.5, 2026, pd.Timestamp("2026-09-08T12:00Z"), True, "x", None)

    def _row(value):
        schema = {getattr(c, "field", None) or "_" for c in columns} | extra_fields
        return pd.Series({name: value for name in schema})

    unformattable, not_exercisable = [], []
    for col in columns:
        kind = getattr(col, "kind", "text")
        tries = [BY_KIND[kind]] if kind in BY_KIND else list(CANDIDATES)
        errors = []
        for value in tries or CANDIDATES:
            try:
                if isinstance(col.format(_row(value)), str):
                    errors = []
                    break
            except Exception as exc:                               # noqa: BLE001
                errors.append(exc)
        else:
            if kind in BY_KIND:                # a typed column gets one honest attempt, then
                for value in CANDIDATES:       # the general set before it is called broken
                    try:
                        if isinstance(col.format(_row(value)), str):
                            errors = []
                            break
                    except Exception as exc:                       # noqa: BLE001
                        errors.append(exc)
        if not errors:
            continue
        # A render that closes over a variable local to its panel cannot be exercised out of
        # that panel. That is this harness's boundary, and it is named rather than hidden.
        if all(isinstance(e, NameError) for e in errors):
            not_exercisable.append(f"{path.name}: {col.field!r} ({col.label!r}) "
                                   f"— render closes over a panel-local: {errors[0]}")
        else:
            unformattable.append(f"{col.field!r} ({col.label!r}): "
                                 f"{type(errors[-1]).__name__}: {errors[-1]}")
    if not_exercisable:
        print("\n  " + "\n  ".join(not_exercisable))

    assert not unformattable, (
        f"{len(unformattable)} column(s) in {path.name} cannot format a row built from their "
        f"own fields:\n  " + "\n  ".join(unformattable))
