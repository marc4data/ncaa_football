"""`model_name` is a join key. A reader must never be shown one.

A276 · cfdb-main-R-4591.

> **MARC, 2026-09-30:** *"cfdb is the name of my VS Code project. My site and brand is
> Marc4Data, or M4D."*

🚨 **A275 RENDERED THE DEPLOYED EDGE FINDER AND READ `cfdb_wtc_c1_own_features_tuned` IN THE
MODEL COLUMN, AND THE MODEL DROPDOWN OFFERED THE SAME STRING** (cfdb-main-R-4567). Two things
are wrong with that string in front of a person: `cfdb` is the VS Code project rather than the
brand, and `wtc_c1` is a modeling session's scaffolding name.

## 🚨 WHY THE BRAND GUARD COULD NEVER HAVE CAUGHT THIS, WHICH IS THE LESSON

`tests/test_the_site_is_branded_m4d.py` and `tests/test_the_published_prose_is_branded_m4d.py`
scan **source**: string literals in `site/`, `description:` prose in dbt. **This `cfdb` was a
DATA VALUE read out of Postgres.** No test that reads the repository can see it, however
carefully it is written — the defect is not in any string anyone wrote.

✅ **SO THIS GUARD ASSERTS THE MECHANISM INSTEAD OF THE STRING: every surface that puts
`model_name` in front of a reader passes it through `lib.models.display_name`.** ❌ It
deliberately does NOT match `cfdb` against database contents — `model_name` legitimately
contains `cfdb_` as an identifier, which is exactly why the brand rule exempts identifier
forms. **The assertion is "it is mapped", not "it does not contain cfdb".**

⚠️ **AND `display_name` IS THE ONE MAP (R-574).** A second copy here would be free to disagree,
and the disagreement would be invisible: each page would look internally consistent while the
workbook shipped a name the page had renamed.

## THE THREE SHAPES, BECAUSE THE CALLABLE CONVENTION DIFFERS BETWEEN THEM

| surface | the callable is handed | A270's trap |
|---|---|---|
| `Col(..., render=f)` | **the ROW** | `display_name(Series)` returns the Series
  unchanged — the column blanks SILENTLY |
| `st.selectbox(..., format_func=f)` | **the VALUE**, and the widget still RETURNS
  the option | a filter that filters on a label is a different bug |
| `workbook` `display={...}` | **the VALUE** | — |

🚨 **`display_name` RETURNS ANYTHING IT DOES NOT RECOGNISE UNCHANGED RATHER THAN RAISING**, so
getting the convention backwards fails quietly in both directions. That is why this file checks
the WIRING rather than a rendered string: a rendered string is only available where a warehouse
is, and CI has none.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
WORKBOOK = SITE / "lib" / "workbook.py"

KEY = "model_name"
MAPPER = "display_name"

# Floors, so a renamed directory or a moved idiom cannot make this pass by walking nothing
# (R-760). Measured at the commit this file was written: 193 Col calls, 19 selectboxes,
# 3 workbook sheets carrying the key.
MIN_COL_CALLS = 150
MIN_SELECTBOXES = 15
MIN_WORKBOOK_SHEETS_WITH_KEY = 3


def _modules():
    for path in sorted(SITE.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def _functions(tree):
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _calls_the_mapper(node, functions) -> bool:
    """Does this callable expression end up calling `models.display_name`?

    Resolves a bare NAME to its `def` in the same module, so the common idiom — a small
    `_model_label(row)` helper beside the page's other renderers — counts, while an unrelated
    renderer does not.
    """
    if node is None:
        return False
    if isinstance(node, ast.Attribute) and node.attr == MAPPER:
        return True                                   # models.display_name, passed directly
    if isinstance(node, ast.Name):
        target = functions.get(node.id)
        return bool(target) and _mentions_mapper(target)
    if isinstance(node, ast.Lambda):
        return _mentions_mapper(node)
    return False


def _mentions_mapper(node) -> bool:
    return any(isinstance(n, ast.Attribute) and n.attr == MAPPER for n in ast.walk(node))


def _col_calls():
    """Every `Col(...)` on the site, as (path, lineno, field, kwargs, tree)."""
    for path, tree in _modules():
        functions = _functions(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Col"):
                continue
            args = [a.value if isinstance(a, ast.Constant) else None for a in node.args]
            kwargs = {k.arg: k.value for k in node.keywords}
            field = args[0] if args else (
                kwargs["field"].value if isinstance(kwargs.get("field"), ast.Constant) else None)
            yield path, node.lineno, field, kwargs, functions


def _selectboxes():
    for path, tree in _modules():
        functions = _functions(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "selectbox"):
                continue
            label = node.args[0].value if (node.args and isinstance(node.args[0], ast.Constant)) \
                else None
            kwargs = {k.arg: k.value for k in node.keywords}
            yield path, node.lineno, label, kwargs, functions


def _workbook_sheets_with_the_key():
    """Workbook calls whose column tuples include `model_name`, with their `display=` keys.

    ⚠️ The mapped value is a NAME (`_model_display`), not an inline call, so it is resolved
    against the module's own `def`s exactly as a `Col`'s `render=` is. Checking for a literal
    `display_name` here would have reported three healthy sheets as offenders — it did, on the
    first run of this file.
    """
    tree = ast.parse(WORKBOOK.read_text(encoding="utf-8"))
    functions = _functions(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fields = []
        for arg in list(node.args) + [k.value for k in node.keywords]:
            if isinstance(arg, (ast.List, ast.Tuple)):
                for element in arg.elts:
                    if (isinstance(element, ast.Tuple) and element.elts
                            and isinstance(element.elts[0], ast.Constant)):
                        fields.append(element.elts[0].value)
        if KEY not in fields:
            continue
        display = None
        for keyword in node.keywords:
            if keyword.arg == "display" and isinstance(keyword.value, ast.Dict):
                display = {k.value: v for k, v in zip(keyword.value.keys, keyword.value.values)
                           if isinstance(k, ast.Constant)}
        yield node.lineno, display, functions


def test_every_model_name_column_renders_the_display_name():
    offenders = []
    for path, lineno, field, kwargs, functions in _col_calls():
        if field != KEY:
            continue
        if not _calls_the_mapper(kwargs.get("render"), functions):
            offenders.append(f"{path.relative_to(ROOT)}:{lineno}  Col({KEY!r}, …) "
                             f"kwargs={sorted(kwargs)}")
    assert not offenders, (
        f"a table column renders the raw `{KEY}` — a reader meets the warehouse key, which "
        f"carries `cfdb` and a modeling session's scaffolding name. Pass `render=` a function "
        f"that calls `models.{MAPPER}` (⚠️ `render` is handed the ROW):\n  "
        + "\n  ".join(offenders))


def test_every_model_picker_shows_the_display_name_and_returns_the_key():
    """⚠️ `format_func` IS THE WHOLE POINT: it changes what is SHOWN, never what is RETURNED.

    Both model pickers filter a query on `model_name = :model`, so the option VALUE has to
    stay the warehouse key. A picker that returned a label would be a different bug.
    """
    offenders = []
    for path, lineno, label, kwargs, functions in _selectboxes():
        if label != "Model":
            continue
        if not _calls_the_mapper(kwargs.get("format_func"), functions):
            offenders.append(f"{path.relative_to(ROOT)}:{lineno}  st.selectbox('Model', …) "
                             f"kwargs={sorted(kwargs)}")
    assert not offenders, (
        f"a model picker offers the raw `{KEY}`. Add `format_func=models.{MAPPER}` — it is "
        f"handed the VALUE and leaves the returned option alone:\n  " + "\n  ".join(offenders))


def test_every_workbook_sheet_carrying_the_key_maps_it():
    """The workbook is the artifact that leaves the building, so it gets the same rule."""
    offenders = []
    for lineno, display, functions in _workbook_sheets_with_the_key():
        mapped = display.get(KEY) if display else None
        if not _calls_the_mapper(mapped, functions):
            offenders.append(f"lib/workbook.py:{lineno}  display={sorted(display or {})}")
    assert not offenders, (
        f"a workbook sheet writes the raw `{KEY}`:\n  " + "\n  ".join(offenders))


def test_this_guard_actually_walked_the_site():
    """🚨 R-760: every assertion above is satisfied by an empty iteration.

    An empty iteration is what a renamed directory, a moved idiom or a changed call shape
    produces — so the populations are asserted rather than assumed, and a floor failing says
    "this guard stopped checking" instead of passing quietly.
    """
    cols = list(_col_calls())
    pickers = list(_selectboxes())
    sheets = list(_workbook_sheets_with_the_key())
    assert len(cols) >= MIN_COL_CALLS, f"only {len(cols)} Col() calls walked"
    assert len(pickers) >= MIN_SELECTBOXES, f"only {len(pickers)} selectboxes walked"
    assert len(sheets) >= MIN_WORKBOOK_SHEETS_WITH_KEY, f"only {len(sheets)} workbook sheets"
    assert [c for c in cols if c[2] == KEY], f"no Col({KEY!r}) found — nothing was checked"
    assert [p for p in pickers if p[2] == "Model"], "no model picker found — nothing checked"


def test_the_resolver_can_tell_a_mapped_renderer_from_an_unmapped_one():
    """⚠️ AN INSTRUMENT NOTHING EXERCISES MIGHT NOT WORK.

    `_calls_the_mapper` resolves a bare name to its `def`. If that resolution broke, every
    assertion above would pass for the wrong reason — so it is run on code written to trip it.
    """
    tree = ast.parse(
        "from lib import models\n"
        "def mapped(row):\n    return models.display_name(row.get('model_name'))\n"
        "def unmapped(row):\n    return str(row.get('model_name'))\n")
    functions = _functions(tree)
    assert _calls_the_mapper(ast.Name(id="mapped", ctx=ast.Load()), functions)
    assert not _calls_the_mapper(ast.Name(id="unmapped", ctx=ast.Load()), functions)
    assert not _calls_the_mapper(ast.Name(id="nonexistent", ctx=ast.Load()), functions)
    assert not _calls_the_mapper(None, functions)
    # passed straight in, which is what a `format_func` does
    assert _calls_the_mapper(
        ast.parse("models.display_name", mode="eval").body, functions)
