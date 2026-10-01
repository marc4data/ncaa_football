"""A season renders `2025`, and both published models render as names.

A274 · cfdb-main-R-4533 (the season) and cfdb-main-R-4537 (the display name).

🚨 TWO DEFECTS ON ONE TABLE, BOTH FOUND BY LOOKING AT A RASTER OF IT (A272's render, read by
Cowork). Model Performance printed the season as **`2,025`** and put a friendly
`M4D Own-Features Model (v1)` beside a truncated raw `random_forest…`.

## WHY THE SEASON ONE IS WORTH A TEST AND NOT JUST A FIX

`lib/table.py` has carried R-280's rule in a comment on `kind="plain"` since R-216 —

> *"A NUMERIC LABEL: no decimal point and NO THOUSANDS SEPARATOR. A season is 2025 and a game
> id is 401752817; a comma in either is a bug, and the workbook has said so in a comment since
> R-216 while the page printed 2,025."*

⚠️ **THE COMMENT DESCRIBED A LIVE DEFECT AND NOBODY NOTICED FOR FIFTY-EIGHT ROUNDS.** §3.2.3's
own lesson: a comment recording a trap does not prevent the trap.

🚨 **SO THIS ASSERTS THE RENDERED STRING, NOT THE `kind`.** A test that asserted
`kind == "plain"` would pass while the defect returned by another route — a new call site, a
`render=` lambda, a change to what `plain` means. **And it DISCOVERS the call sites rather than
restating them** (R-768: a test that builds its own frame asserts that pandas sorts).
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# Fields whose value is a LABEL that happens to be made of digits. A thousands separator in
# any of them is a bug, which is R-280's whole point.
LABEL_FIELDS = {"season", "game_id", "id"}


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return "<expr>"


def declared_label_columns():
    """Every `Col(...)` on the site whose field is a digit-made LABEL, as (file, line, args).

    Discovered from the source, so a NEW `season` column is covered the day it is written.
    """
    found = []
    for path in sorted(SITE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Col"):
                continue
            args = [_literal(a) for a in node.args]
            kwargs = {k.arg: _literal(k.value) for k in node.keywords}
            field = args[0] if args else kwargs.get("field")
            if field in LABEL_FIELDS:
                found.append((path.relative_to(ROOT).as_posix(), node.lineno, args, kwargs))
    return found


def test_the_site_declares_at_least_one_label_column():
    """🚨 R-760: the sweep below is satisfied by an empty iteration, which is what a renamed
    field or a moved directory produces. The floor is asserted, not assumed."""
    found = declared_label_columns()
    assert found, "no Col() with a label field found under site/ — this test checks nothing"
    assert any(args and args[0] == "season" for _, _, args, _ in found), (
        "no `season` column found — Model Performance declares one")


def test_every_label_column_renders_without_a_thousands_separator():
    """THE RENDERED STRING, from the page's own declaration, for a four-digit value."""
    import sys
    sys.path.insert(0, str(SITE))
    from lib.table import Col                                        # noqa: PLC0415

    offenders = []
    for where, lineno, args, kwargs in declared_label_columns():
        if kwargs.get("render") == "<expr>" or "render" in kwargs:
            continue        # a custom renderer is its own contract, tested where it lives
        if "<expr>" in args or "<expr>" in kwargs.values():
            continue
        field = args[0]
        col = Col(*args, **kwargs)
        rendered = col.format({field: 2025})
        if rendered != "2025":
            offenders.append(f"{where}:{lineno}  Col({args!r}, {kwargs!r}) -> {rendered!r}")
    assert not offenders, (
        "a label column renders a thousands separator — R-280: a season is 2025 and a game id "
        "is 401752817, and a comma in either is a bug:\n  " + "\n  ".join(offenders))


def test_the_break_this_pins_actually_moves_the_value():
    """🚨 R-843: a pinned value is only a pin if the break moves it.

    `kind="num"` is the defect that was shipped. If it ever renders `2025` too, the assertion
    above has stopped being able to fail and this says so.
    """
    import sys
    sys.path.insert(0, str(SITE))
    from lib.table import Col                                        # noqa: PLC0415

    assert Col("season", "Season", "num", dp=0).format({"season": 2025}) == "2,025", (
        "the staged break no longer produces a comma, so the test above proves nothing")


def test_the_season_column_still_opens_newest_first():
    """⚠️ CHANGING THE KIND CHANGES THE SORT, AND THAT IS NOT PART OF THE FIX.

    `first_order` defaults to `desc` for `num` and `asc` for everything else, so moving the
    season column to `plain` would have flipped the newest season off the top of the first
    click. `opens="desc"` carries it; this pins the behaviour rather than the keyword.
    """
    import sys
    sys.path.insert(0, str(SITE))
    from lib.table import Col                                        # noqa: PLC0415

    seasons = [(w, ln, a, k) for w, ln, a, k in declared_label_columns()
               if a and a[0] == "season"]
    assert seasons, "no season column to check"
    for where, lineno, args, kwargs in seasons:
        assert Col(*args, **kwargs).first_order == "desc", (
            f"{where}:{lineno} season opens ascending — the newest season should lead")


def test_both_published_models_render_as_names_not_one_of_each():
    """A272 shipped `DISPLAY_NAMES` with one of the two published models in it.

    🚨 THE ASYMMETRY IS THE DEFECT. One friendly name beside one raw key reads as a rendering
    fault; two keys would at least be consistent. ⚠️ And nothing withdrawn belongs in the map
    (§3.2.3) — a display name for a model the site does not show is prose nothing renders.
    """
    import sys
    sys.path.insert(0, str(SITE))
    from lib import models                                           # noqa: PLC0415

    missing = sorted(models.PUBLISHED - set(models.DISPLAY_NAMES))
    assert not missing, f"published models with no display name: {missing}"
    extra = sorted(set(models.DISPLAY_NAMES) - models.PUBLISHED)
    assert not extra, f"display names for models this site does not publish: {extra}"
    for name in models.PUBLISHED:
        shown = models.display_name(name)
        assert shown != name, f"{name} still renders as its own key"
        assert "cfdb" not in shown.lower(), f"{name} display name says cfdb: {shown!r}"


@pytest.mark.parametrize("value,expected", [(2025, "2025"), (401752817, "401752817")])
def test_plain_is_the_kind_that_carries_the_rule(value, expected):
    """R-280's two examples, from its own sentence, asserted rather than quoted."""
    import sys
    sys.path.insert(0, str(SITE))
    from lib.table import Col                                        # noqa: PLC0415

    assert Col("x", "X", "plain").format({"x": value}) == expected
