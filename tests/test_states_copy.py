"""The state cards' copy — the title must not contradict the body. R-500.

`site/lib/states.py` is imported by every data-bearing section on the site, so its copy is
eighteen pages' copy. B074 found `degraded()` hardcoding "Not built yet" on a card whose own
explanation said the opposite — srv_team_week IS built and IS published, and it was that
team's ROW that was absent — and correctly refused to fix it from a session that owns one
page.

These tests exist because the defect is invisible to every other check in the suite: the
string was right for five callers and wrong for three, and nothing compared a title to the
sentence printed underneath it.
"""
import ast
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "site" / "lib" / "states.py"
SOURCE = STATES.read_text()


def _stub_streamlit():
    """Records what reached st.markdown, so a test can read the rendered card."""
    calls = []
    stub = types.ModuleType("streamlit")
    stub.markdown = lambda *a, **k: calls.append(a[0] if a else "")
    for name in ("caption", "subheader", "write", "button", "columns", "container"):
        setattr(stub, name, lambda *a, **k: None)

    def _cache(*a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return lambda f: f

    stub.cache_data = stub.cache_resource = _cache
    return stub, calls


def _states_module():
    import importlib
    stub, calls = _stub_streamlit()
    saved = sys.modules.get("streamlit")
    sys.modules["streamlit"] = stub
    path_added = str(ROOT / "site") not in sys.path
    if path_added:
        sys.path.insert(0, str(ROOT / "site"))
    try:
        mod = importlib.reload(importlib.import_module("lib.states"))
        return mod, calls, saved, path_added
    except Exception:
        if saved is not None:
            sys.modules["streamlit"] = saved
        raise


def _restore(saved, path_added):
    import importlib
    if saved is not None:
        sys.modules["streamlit"] = saved
    else:
        sys.modules.pop("streamlit", None)
    importlib.reload(importlib.import_module("lib.states"))
    if path_added and str(ROOT / "site") in sys.path:
        sys.path.remove(str(ROOT / "site"))


def test_degraded_defaults_to_the_title_it_always_had():
    """The five callers that ARE about an unbuilt object must not move."""
    mod, calls, saved, added = _states_module()
    try:
        mod.degraded("srv_thing", "It has not been built.")
        card = calls[-1]
        assert "<div class='cfdb-state-title'>Not built yet</div>" in card
    finally:
        _restore(saved, added)


def test_degraded_can_say_something_true_when_the_thing_IS_built():
    """R-500's actual repair. A caller whose body says the data exists can say so up top."""
    mod, calls, saved, added = _states_module()
    try:
        mod.degraded("srv_team_week", "cfdb holds no week-by-week record for this team.",
                     title="No data for this team")
        card = calls[-1]
        assert "<div class='cfdb-state-title'>No data for this team</div>" in card
        assert "Not built yet" not in card, "the default leaked through the override"
    finally:
        _restore(saved, added)


def test_no_caller_claims_not_built_while_its_own_words_say_it_is_built():
    """⚠️ THE ONE THAT WOULD HAVE CAUGHT R-500, AND WOULD CATCH THE NEXT ONE.

    Reads every states.degraded(...) call across the site and, for any whose explanation
    asserts the thing EXISTS, requires an explicit title. A card that says "the ratings
    themselves are built" under the words "Not built yet" tells the reader the opposite of
    the sentence beneath it, and no other test in this suite compares the two.

    Deliberately keyed on phrases that CLAIM EXISTENCE rather than on a list of file names —
    a name list is a list nobody maintains, and this project has said so twice.
    """
    claims_built = re.compile(
        r"(themselves are built|is now in the warehouse|are built|holds no|"
        r"is built|already built|exists)", re.IGNORECASE)

    offenders = []
    for path in sorted((ROOT / "site").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name != "degraded":
                continue
            has_title = any(kw.arg == "title" for kw in node.keywords)
            # every string literal in the call, positional or keyword
            text = " ".join(
                n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str))
            if claims_built.search(text) and not has_title:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert not offenders, (
        "these degraded() cards assert the thing EXISTS in their body while defaulting to "
        f"the title 'Not built yet': {offenders}. Pass an explicit title.")


def test_the_three_titles_are_distinct_so_a_reader_can_tell_the_states_apart():
    """Empty, Degraded and Error must not converge on one another's copy."""
    titles = re.findall(r"cfdb-state-title'>([^<{]+)<", SOURCE)
    assert "Nothing to show" in titles
    assert "Could not load this section" in titles
    assert len(set(titles)) == len(titles), f"two states share a title: {titles}"
