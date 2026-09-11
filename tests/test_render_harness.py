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
_REAL_RUN = subprocess.run   # A094: test_heartbeat patches subprocess.run globally and it leaks

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
        result = _REAL_RUN([sys.executable, str(probe)], capture_output=True, text=True)
        assert "RAISED_ON_DUNDER" in result.stdout, (
            f"removing the exemption did not make a dunder raise: {result.stdout}{result.stderr}")
