"""The harness's own guard (R-631). Five requirements, five assertions, one break.

⚠️ A HARNESS NOBODY TESTS IS THE THING R-571 IS ABOUT. Five rounds re-implemented this pattern
and A093 had to repair one that could not model nested columns; the repair was found by running
a break, not by reading the code.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import render_harness  # noqa: E402


def test_an_unknown_streamlit_method_raises_LOUDLY():
    """🚨 A085: the stub omitted `line_chart`, the page's only chart call, and the resulting
    AttributeError was rendered by states.section as an Error state — indistinguishable from a
    page defect."""
    st, _captured, _charts = render_harness.build()
    st.caption("this one is provided")
    with pytest.raises(render_harness.HarnessGap) as caught:
        st.balloons()
    assert "st.balloons()" in str(caught.value)
    assert "NOT A PAGE DEFECT" in str(caught.value)


def test_except_Exception_CANNOT_swallow_a_harness_gap():
    """The reason HarnessGap derives from BaseException. `states.section` catches Exception to
    turn a fault into an Error state; a gap must escape that or it renders AS the page."""
    st, _c, _ch = render_harness.build()
    swallowed = False
    try:
        try:
            st.balloons()
        except Exception:                                          # noqa: BLE001
            swallowed = True
    except render_harness.HarnessGap:
        pass
    assert not swallowed, "a page-level `except Exception` swallowed the gap"


def test_a_DUNDER_does_not_raise():
    """⚠️ B082, AND THIS ONE HID ITS OWN EVIDENCE. pytest reads `__file__` on a module WHILE
    FORMATTING A FAILURE, so raising on a dunder turned a red test into INTERNALERROR — the
    report of the break was replaced by a crash in the reporter."""
    st, _c, _ch = render_harness.build()
    with pytest.raises(AttributeError):
        st.__file__          # noqa: B018 — the point is that it is AttributeError, not HarnessGap
    container = render_harness.Recorder([])
    with pytest.raises(AttributeError):
        container.__deepcopy__   # noqa: B018


def test_a_column_can_make_columns():
    """⚠️ A093: the legend nests st.columns(2) inside a column. A generic recorder returns None
    and `zip(None, …)` raises, which looks like a page defect."""
    st, captured, _ch = render_harness.build()
    outer = st.columns([1, 2])
    assert len(outer) == 2
    inner = outer[1].columns(2)
    assert len(inner) == 2
    inner[0].markdown("drawn into a nested column")
    assert any("nested column" in c for c in captured)


def test_assert_captured_refuses_an_EMPTY_capture():
    """⚠️ B079: a silent absence reads as a pass. A091 asserted the popover was captured before
    printing anything."""
    render_harness.assert_captured("<div class='cfdb-legend'>x</div>", "cfdb-legend")
    with pytest.raises(AssertionError) as caught:
        render_harness.assert_captured("", "cfdb-legend")
    assert "EMPTY CAPTURE" in str(caught.value)


def test_the_provided_list_is_named_and_covers_every_chart_call_in_the_site():
    """Requirement 5: a gap is legible rather than latent. Asserted against the real pages, so a
    new chart type on a page fails HERE rather than mid-render."""
    import re
    calls = set()
    for path in (ROOT / "site" / "views").glob("*.py"):
        calls |= set(re.findall(r"\bst\.([a-z_]+chart|map|pyplot)\s*\(", path.read_text()))
    missing = sorted(c for c in calls if c not in render_harness.PROVIDED)
    assert not missing, f"pages call st.{missing} and the harness does not provide it"


def test_the_dunder_exemption_can_actually_fail():
    """🚨 PART 5's BREAK FOR R-631, AND IT IS THE DUNDER CASE ON PURPOSE — the one that hid its
    own evidence.

    Runs a scratch copy of the harness with the dunder exemption REMOVED and asserts that
    reading `__file__` then raises HarnessGap. ⚠️ In-process rather than under pytest, because
    the whole point of B082's failure is that a raising dunder breaks the REPORTER — so
    observing it must not go through one.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "render_harness.py"
        source = (ROOT / "tests" / "render_harness.py").read_text()
        broken = source.replace(
            '        if name.startswith("__"):\n            raise AttributeError(name)\n'
            '        raise HarnessGap(', '        raise HarnessGap(', 1)
        assert broken != source, "the dunder exemption moved — update this test"
        scratch.write_text(broken)
        probe = Path(tmp) / "probe.py"
        probe.write_text(
            "import sys; sys.path.insert(0, %r)\n"
            "import render_harness as h\n"
            "st, _c, _ch = h.build()\n"
            "try:\n"
            "    st.__file__\n"
            "except h.HarnessGap:\n"
            "    print('RAISED_ON_DUNDER')\n"
            "except AttributeError:\n"
            "    print('exempt')\n" % str(scratch.parent))
        result = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
        assert "RAISED_ON_DUNDER" in result.stdout, (
            f"removing the exemption did not make a dunder raise: {result.stdout}{result.stderr}")


# --- 🚨 R-612: the detector is a STRING, and a string nobody pinned is a guard that can go blind

_STATES = ROOT / "site" / "lib" / "states.py"
_THEME = ROOT / "site" / "lib" / "theme.py"


def _function_source(path, name):
    """One function's source, by AST, so a comment mentioning the class cannot satisfy this."""
    import ast
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(path.read_text(), node) or ""
    raise AssertionError(f"{path.name} has no function named {name!r} — "
                         f"the harness's detector is pinned to a function that no longer exists")


def test_the_ERROR_detector_matches_what_states_py_ACTUALLY_DRAWS():
    """🚨 B092's GUARD RESTS ON `ERROR_CARD = "cfdb-error"` AND NOTHING ASSERTED THE JOIN.

    `assert_no_error_card` decides whether a panel died by looking for that class in the drawn
    markup. ⚠️ RENAME THE CSS CLASS IN `states.py` — a cosmetic change nobody would stop in
    review — AND THE GUARD PASSES FOREVER, SILENTLY, ON EVERY PANEL IN THE SUITE. It cannot
    tell that it has stopped measuring, which is the precise property it was built to remove.

    ✅ THE COUPLING GOES INTO THE TEST, which is B087's precedent: assert the join so a move
    FAILS LOUDLY rather than going quiet.

    ⚠️ BOTH RENDER PATHS, NOT ONE. `error()` is a query that failed and `render_failed()` is a
    renderer that failed — R-630 split them deliberately — so a change could keep the class on
    one and take it off the other, and half the guard would go blind with the suite green.
    """
    for name in ("error", "render_failed"):
        body = _function_source(_STATES, name)
        assert render_harness.ERROR_CARD in body, (
            f"THE GUARD'S DETECTOR NO LONGER MATCHES WHAT THE SITE DRAWS. "
            f"`render_harness.ERROR_CARD` is {render_harness.ERROR_CARD!r} and "
            f"`states.{name}()` does not emit it any more — so "
            f"`assert_no_error_card` now returns clean on EVERY panel, including one that "
            f"died on its first line, and every panel test in this suite is blind. "
            f"Update ERROR_CARD to whatever {name}() emits; do not delete this assertion.")


def test_the_DEGRADED_detector_matches_too_because_telling_them_apart_is_the_point():
    """⚠️ THE RECORDER'S ABILITY TO TELL DEGRADED FROM ERROR IS WHAT KEEPS IT FROM BEING BLUNT.

    A Degraded panel is an honest state a test may legitimately render — "srv_x has not been
    built yet" — and B092 made only the error card fatal for exactly that reason. That
    distinction rests on the same unpinned string.
    """
    body = _function_source(_STATES, "degraded")
    assert render_harness.DEGRADED_CARD in body, (
        f"`render_harness.DEGRADED_CARD` is {render_harness.DEGRADED_CARD!r} and "
        f"`states.degraded()` no longer emits it — so the guard can no longer tell an honest "
        f"Degraded panel from a panel that raised, and it will either start failing tests "
        f"that are correct or stop failing ones that are not.")


def test_both_cards_are_actually_STYLED_so_neither_is_an_unstyled_div():
    """⚠️ A CLASS EMITTED AND NEVER STYLED IS A THIRD FAILURE THIS PINS CHEAPLY.

    `theme.py` carries the stylesheet, so a rename that updated `states.py` and not the CSS
    would leave the guard working and the card looking like body text. Cowork's census of this
    string said three occurrences in the tree; there are six — `theme.py` styles both classes
    and `views/performance.py` emits the degraded one directly.
    """
    css = _THEME.read_text()
    for token in (render_harness.ERROR_CARD, render_harness.DEGRADED_CARD):
        assert f".{token}" in css, (
            f"`{token}` is emitted by states.py and has no rule in theme.py, so the card "
            f"renders unstyled")
