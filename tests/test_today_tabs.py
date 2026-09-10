"""Today's two tabs, and the captions that say which dataset each panel reads.

R-573 (the split) and R-574 (the captions). Both guards here exist because the page has
already been wrong in exactly the ways they check:

  R-574  the page carried ONE `dataset_caption("Looking Back", "srv_game")` while reading
         FIVE views. Four of six sections named the wrong dataset, and because the caption
         renders a LINK to /dictionary?table=..., a reader clicking it from the Leaderboards
         landed on the wrong table. The right answer was in the file the whole time — every
         panel names its own view in `states.section` — and was visible only in the Error
         state.

  R-573  B075's lesson, quoted from its own docstring: the assignment test "fails the moment
         a panel exists unassigned". A panel dropped during a move is the most likely defect
         of a tab split and nothing else in this project would notice.

⚠️ THE POINT OF test_the_views_named_in_sections_are_exactly_the_views_the_module_reads IS
THAT THERE IS NO SECOND LIST. The caption is emitted from `states.section`'s own `view`
argument, so a caption cannot disagree with the Error state beside it. What CAN still drift
is the page reading a view no section names — a new panel with a new query — and that is what
this asserts. It is the same two-lists-must-agree shape as
ci/check_publish_build_agreement.py, one layer up.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
TREE = ast.parse(SOURCE)


@pytest.fixture(scope="module")
def today():
    import importlib
    return importlib.import_module("views.today")


def _section_views():
    """Every view named in a `states.section(...)` call, in source order."""
    out = []
    for node in ast.walk(TREE):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section" and node.args
                and isinstance(node.args[0], ast.Constant)):
            out.append(node.args[0].value)
    return out


def _queried_views():
    """Every `from srv_*` in the module's SQL."""
    return set(re.findall(r"\bfrom\s+(srv_[a-z_]+)", SOURCE, re.IGNORECASE))


# --- R-573, the split -------------------------------------------------------------------

def _panels_defined():
    """Every panel this module defines, WITHOUT consulting TABS.

    🚨 THE INDEPENDENCE IS THE WHOLE TEST. The first draft of this built its "defined" set by
    filtering module functions against the names already in TABS, which made the assertion
    circular: dropping a panel from TABS also dropped it from the expectation, and the staged
    break passed green. B075's own rule — "a test that passes both ways is not a test" —
    caught in the act, by running the break rather than by reading the code.

    So a panel is defined STRUCTURALLY: a module-level function taking exactly `(scope,
    depth)` and annotated `-> None`. That is the signature body() calls them through, and it
    excludes the query helpers — `_team_yardage(scope, depth)` takes the same two arguments
    and is not a panel, which is why the return annotation is part of the rule rather than
    decoration.
    """
    out = set()
    for node in TREE.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        args = [a.arg for a in node.args.args]
        returns_none = isinstance(node.returns, ast.Constant) and node.returns.value is None
        if args == ["scope", "depth"] and returns_none:
            out.add(node.name)
    return out


def test_every_panel_is_assigned_to_exactly_one_tab(today):
    """⚠️ A PANEL SILENTLY DROPPED DURING A MOVE IS THIS ROUND'S MOST LIKELY DEFECT.

    B075 built this for Matchup and its reasoning transfers unchanged: body() renders only
    the active tab's panels, so an unassigned panel does not error — it simply stops being
    on the page, on every tab, forever.
    """
    assigned = [name for _slug, _label, panels in today.TABS for name in panels]
    assert len(assigned) == len(set(assigned)), f"a panel is on two tabs: {assigned}"
    assert set(assigned) == _panels_defined(), (
        f"TABS assigns {sorted(set(assigned))}; the module defines "
        f"{sorted(_panels_defined())}")


def test_every_named_panel_actually_resolves_to_a_function(today):
    """The cost of naming panels instead of referencing them: a typo in TABS is a KeyError at
    render rather than at import. Naming is what makes the laziness testable, so the typo is
    caught here instead."""
    for _slug, _label, panels in today.TABS:
        for name in panels:
            resolved = vars(today).get(name)
            assert callable(resolved), f"TABS names {name!r}, which is not a function here"
            assert getattr(resolved, "__name__", None) == name


def test_an_unknown_tab_slug_falls_back_rather_than_raising(today, monkeypatch):
    """AC-G.11, and scores.py's own rule: a hand-edited `?tab=` is noise, not a request."""
    monkeypatch.setattr(today.params, "get", lambda name, *a, **k:
                        "not-a-tab" if name == "tab" else None)
    assert today._active_tab() == today.TABS[0]


def test_the_default_tab_is_looking_back(today):
    """Six panels against one. Defaulting to the empty tab would be a worse page."""
    assert today.TABS[0][0] == "back"


# --- R-574, the captions ----------------------------------------------------------------

def test_the_views_named_in_sections_are_exactly_the_views_the_module_reads():
    """🚨 THE GUARD THAT MAKES "NO SECOND LIST" TRUE RATHER THAN INTENDED.

    A panel added with a new query and no section, or a section pointed at a view the page
    does not read, both land here.
    """
    assert set(_section_views()) == _queried_views(), (
        f"sections name {sorted(set(_section_views()))} but the module reads "
        f"{sorted(_queried_views())}")


def test_every_section_states_its_dataset_and_every_label_is_used(today):
    """Both directions. A view with no label renders no caption — the silent-guard shape this
    project has been bitten by three times — and a label no section names is dead copy."""
    named = set(_section_views())
    assert named == set(today.DATASETS), (
        f"sections name {sorted(named)}; DATASETS has {sorted(today.DATASETS)}")
    for view, label in today.DATASETS.items():
        assert label and not label.startswith("srv_"), \
            f"{view} label {label!r} is an identifier, not front-of-house copy (AC-G.7)"


def test_no_section_call_omits_the_dataset_label():
    """The caption is emitted BY states.section, so a section without `dataset=` is a panel
    that silently states nothing."""
    missing = []
    for node in ast.walk(TREE):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section" and node.args
                and isinstance(node.args[0], ast.Constant)):
            if not any(k.arg == "dataset" for k in node.keywords):
                missing.append((node.args[0].value, node.lineno))
    assert not missing, f"states.section without a dataset label: {missing}"


def test_the_page_level_dataset_caption_is_gone():
    """R-574's original defect, asserted so it cannot come back: one caption at the top of a
    page that reads five views.

    ⚠️ IT WALKS THE AST RATHER THAN GREPPING, and the first draft of this test grepped and
    failed on the COMMENT in body() that explains what was removed. _profile's own docstring
    records the same trap from the other side — a source grep "cannot tell page copy from a
    comment discussing page copy" — and works around it by not quoting the banned phrase.
    Parsing does not need the workaround: a call is a Call node and a comment is not a node
    at all.
    """
    calls = [n for n in ast.walk(TREE)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "dataset_caption"]
    assert not calls, (
        f"today.py calls dataset_caption directly at line(s) "
        f"{[n.lineno for n in calls]} — it belongs to states.section now (R-574)")
