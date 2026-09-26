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


def _view_names(node, assigned):
    """The view name(s) a `states.section(...)` first argument can resolve to.

    🚨 A225 WIDENED THIS, AND THE REASON IS A REAL PANEL RATHER THAN A CONVENIENCE. The
    player boards read `srv_player_stats` with every week selected and `srv_player_game_log`
    with one week picked — two sources behind one board, because the season view publishes no
    `week`. `states.section`'s `view` argument is what the Error state AND the dataset caption
    both render from (R-574), so it has to move with the source or the reader is told the
    season totals came from the game log.

    ⚠️ THE ALTERNATIVE WAS TO KEEP A LITERAL AND LET THE CAPTION BE WRONG HALF THE TIME. This
    check exists to make a panel declare what it reads; a panel that reads two things and says
    so is the case it should cover, not the case it should refuse.

    ⚠️ IT RESOLVES ONE HOP AND NO FURTHER — a Constant, or a Name bound to a conditional over
    constants. Anything cleverer than that is a view name this file cannot verify, and it is
    better for the assertion below to fail loudly on it than for the walker to guess.
    """
    if isinstance(node, ast.Constant):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _view_names(node.body, assigned) + _view_names(node.orelse, assigned)
    if isinstance(node, ast.Name):
        return assigned.get(node.id, [])
    return []


def _section_views():
    """Every view named in a `states.section(...)` call, in source order."""
    assigned = {}
    for node in ast.walk(TREE):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            names = _view_names(node.value, {})
            if names and all(isinstance(n, str) and n.startswith("srv_") for n in names):
                assigned.setdefault(node.targets[0].id, []).extend(names)
    out = []
    for node in ast.walk(TREE):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section" and node.args):
            out.extend(_view_names(node.args[0], assigned))
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


def test_every_section_states_its_dataset(today):
    """A view with no label renders no caption — the silent-guard shape this project has been
    bitten by three times.

    ⚠️ R-583 WEAKENED THIS FROM AN EQUALITY TO A SUBSET, AND THE REASON SHOULD NOT BE LOST.
    `DATASETS` moved to `lib/datasets.py` so Matchup can consume it instead of declaring a
    second table naming the same views. It is now a SITE-WIDE table, so "every label is used"
    stopped being a statement about Today: it holds six keys Today does not read, deliberately,
    because §3 rule 3.1 says a shared-module change ships the labels and B's round wires B's
    call sites.

    ⚠️ THE DEAD-COPY DIRECTION IS THEREFORE UNGUARDED RIGHT NOW, and pretending otherwise would
    be worse than saying so. The honest version — every key in datasets.py is named by a
    `states.section` somewhere under site/views/ — cannot pass until Matchup's call sites land,
    and a guard that ships already exempted is not a guard. It belongs with B's round.
    """
    named = set(_section_views())
    missing = named - set(today.DATASETS)
    assert not missing, f"sections name views with no label in datasets.py: {sorted(missing)}"
    for view, label in today.DATASETS.items():
        assert label and not label.startswith("srv_"), \
            f"{view} label {label!r} is an identifier, not front-of-house copy (AC-G.7)"


def test_no_section_call_omits_the_dataset_label():
    """The caption is emitted BY states.section, so a section that names no dataset ANYWHERE is
    a panel that silently states nothing.

    🚨 A239 (cfdb-main-R-3232) WIDENED THIS RATHER THAN WEAKENING IT. Marc asked for one
    `Dataset:` line on a panel that reads two views, so the KPI row's nested distribution section
    now omits `dataset=` and its label rides on the OUTER section's `dataset_also`. **The
    property that matters was never "every section passes `dataset=`" — it is "every view a panel
    reads is NAMED to the reader"**, and this now asserts exactly that: an omission is allowed
    only where some enclosing section demonstrably carries that view's label.

    ⚠️ A test that had simply been relaxed to `if node.lineno != 4785` would have stopped
    checking the thing it exists for.
    """
    # every table name any section hands to `dataset_also`, i.e. labels carried by a parent
    carried = set()
    for node in ast.walk(TREE):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section"):
            continue
        for kw in node.keywords:
            if kw.arg != "dataset_also":
                continue
            for element in getattr(kw.value, "elts", []):
                parts = getattr(element, "elts", [])
                if len(parts) == 2 and isinstance(parts[1], ast.Constant):
                    carried.add(parts[1].value)

    missing = []
    for node in ast.walk(TREE):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section" and node.args
                and isinstance(node.args[0], ast.Constant)):
            view = node.args[0].value
            if not any(k.arg == "dataset" for k in node.keywords) and view not in carried:
                missing.append((view, node.lineno))
    assert not missing, (
        f"states.section names no dataset and no other section carries it: {missing}")


def test_A_CARRIED_DATASET_LABEL_REALLY_REACHES_THE_READER():
    """🚨 THE OTHER HALF OF THE TEST ABOVE, because "some parent mentions it" is a claim about
    the AST and the reader sees the DOM. A view listed in `dataset_also` must actually be
    rendered, with its own dictionary link — otherwise the guard above has been satisfied by a
    keyword nobody emits."""
    from lib.datasets import DATASETS
    carried = []
    for node in ast.walk(TREE):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "section"):
            continue
        for kw in node.keywords:
            if kw.arg == "dataset_also":
                for element in getattr(kw.value, "elts", []):
                    parts = getattr(element, "elts", [])
                    if len(parts) == 2 and isinstance(parts[1], ast.Constant):
                        carried.append(parts[1].value)
    assert carried, "no section carries another's label, so this test asserts nothing (R-2254)"
    import streamlit as st
    from lib import table
    seen = []
    real = st.markdown
    st.markdown = lambda html, **k: seen.append(html)
    try:
        table.dataset_caption(DATASETS["srv_week_summary"], "srv_week_summary",
                              [(DATASETS[v], v) for v in carried])
    finally:
        st.markdown = real
    html = seen[0]
    for view in carried:
        assert f"table={view}" in html, f"{view} is carried but never linked: {html}"
        assert DATASETS[view] in html, f"{view}'s label is missing from the caption"


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


# ── A243 — one Dataset line per tab, built from the sections themselves ─────────────────────

def test_EVERY_TAB_DECLARES_ITS_VIEWS_IN_ONE_LINE(today):
    """🚨 A243 (cfdb-main-R-3328). ONE `cfdb-dataset` div per tab, naming EVERY view that tab's
    sections declare.

    > **MARC, 2026-09-26:** *"Consolidate instead of wasting 3 lines, 2 of which don't seem tied
    > to anything."*

    📊 MEASURED BEFORE: Looking Back rendered **eight** divs, `srv_game` twice, because
    `states.section` emits its caption BEFORE its panel — so the line under the KPI row belonged
    to the next panel down.

    🚨 THIS ASSERTS THE HARD PART, WHICH IS NOT THE COUNT. R-574's defect was a single
    hand-written caption on a page reading five views: one line, and a link that sent a reader to
    the wrong table. **So the line must name every view the tab's own sections declare** — the
    count being 1 is worthless without that.
    """
    tabs = {slug: panels for slug, _label, panels in today.TABS}
    assert tabs, "no tabs found (R-2254)"
    for slug, panels in tabs.items():
        declared = set()
        for name in panels:
            fn = next((n for n in ast.walk(TREE)
                       if isinstance(n, ast.FunctionDef) and n.name == name), None)
            assert fn is not None, f"{slug} names a panel that does not exist: {name}"
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call)
                        and getattr(node.func, "attr", "") == "section"):
                    continue
                takes_dataset = any(k.arg == "dataset" for k in node.keywords)
                if takes_dataset and node.args and isinstance(node.args[0], ast.Constant):
                    declared.add(node.args[0].value)
                for kw in node.keywords:
                    if kw.arg != "dataset_also":
                        continue
                    for el in getattr(kw.value, "elts", []):
                        parts = getattr(el, "elts", [])
                        if len(parts) == 2 and isinstance(parts[1], ast.Constant):
                            declared.add(parts[1].value)
        assert declared, f"tab {slug!r} declares no dataset at all"
        # every declared view must be reachable from `DATASETS`, or the line cannot name it
        from lib.datasets import DATASETS
        missing = sorted(v for v in declared if v not in DATASETS)
        assert not missing, (
            f"tab {slug!r} declares view(s) with no entry in DATASETS, so the consolidated line "
            f"cannot name them: {missing}")


def test_THE_TAB_SLOT_COLLECTS_DEDUPES_AND_STAYS_SILENT_WHEN_EMPTY():
    """🚨 THE THREE PROPERTIES THE CONSOLIDATED LINE RESTS ON, asserted at the collector rather
    than through a render, so they hold without a database.

    ⚠️ **Silence when nothing registered is AC-G.11**: `Dataset:` with an empty tail would be an
    absence that does not say which absence it is.
    """
    from lib import shell
    import streamlit as st
    seen = []
    real = st.markdown
    st.markdown = lambda html, **k: seen.append(html)
    try:
        # 1 — with no slot open, a section renders in place (the other seventeen pages' path)
        assert shell.dataset_slot() is None
        assert shell.register_dataset("Schedule", "srv_game") is False

        # 2 — with a slot open it collects, and DE-DUPLICATES on the pair
        class _Slot:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        shell._DATASET_SLOT, shell._DATASETS_SEEN = _Slot(), []
        for lab, view in (("Game results and market lines", "srv_game"),
                          ("AP and Coaches polls", "srv_rankings"),
                          ("Game results and market lines", "srv_game")):
            assert shell.register_dataset(lab, view) is True
        assert shell._DATASETS_SEEN == [("Game results and market lines", "srv_game"),
                                        ("AP and Coaches polls", "srv_rankings")], \
            f"srv_game was not de-duplicated: {shell._DATASETS_SEEN}"
        seen.clear()
        shell.close_dataset_slot()
        assert len(seen) == 1, f"the slot rendered {len(seen)} captions, not one"
        assert seen[0].count("<a ") == 2, "each view must keep its OWN dictionary link"
        assert "table=srv_game" in seen[0] and "table=srv_rankings" in seen[0]

        # 3 — nothing registered renders NOTHING, not an empty `Dataset:`
        shell._DATASET_SLOT, shell._DATASETS_SEEN = _Slot(), []
        seen.clear()
        shell.close_dataset_slot()
        assert seen == [], f"an empty tab still rendered: {seen}"
    finally:
        st.markdown = real
        shell._DATASET_SLOT, shell._DATASETS_SEEN = None, []


def test_SECTION_REGISTERS_EVERY_VIEW_IT_IS_GIVEN():
    """🚨 A243. THE GAP A STAGED BREAK FOUND, AND IT IS R-768's SHAPE.

    `test_EVERY_TAB_DECLARES_ITS_VIEWS_IN_ONE_LINE` walks `today.py`'s AST — it checks what the
    sections DECLARE. **Adding a condition inside `states.section` that skips registering one
    view left every test green**, because no test watched the registration itself. The tab would
    have rendered a line silently missing a source, which is R-574's defect wearing a new hat.

    ⚠️ ASSERTED AT THE COLLECTOR, NOT THROUGH A RENDER, and deliberately so: a render needs a
    database, CI has none, and a test that skips in CI is the defect PART 0 of this round just
    finished correcting on the Methodology page.
    """
    import streamlit as st
    from lib import shell, states

    class _Slot:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    seen = []
    real = st.markdown
    st.markdown = lambda html, **k: seen.append(html)
    shell._DATASET_SLOT, shell._DATASETS_SEEN = _Slot(), []
    try:
        GIVEN = [("srv_week_summary", "The week in one row",
                  [("Distributions, by week", "srv_week_metric_distribution")]),
                 ("srv_game", "Game results and market lines", []),
                 ("srv_rankings", "AP and Coaches polls", [])]
        for view, label, also in GIVEN:
            with states.section(view, dataset=label, dataset_also=also):
                pass
        registered = {v for _lab, v in shell._DATASETS_SEEN}
        expected = {v for v, _l, _a in GIVEN} | {
            v for _v, _l, also in GIVEN for _lab, v in also}
        assert registered == expected, (
            f"a section did not register the view it declared: missing "
            f"{sorted(expected - registered)}, unexpected {sorted(registered - expected)}")
        # and nothing rendered in place while the slot was open
        assert not [h for h in seen if "cfdb-dataset" in h], (
            "a caption rendered in place while a tab slot was open — it would appear twice")
    finally:
        st.markdown = real
        shell._DATASET_SLOT, shell._DATASETS_SEEN = None, []
