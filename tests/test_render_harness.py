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


# --- 🚨 R-617: THE ASSERTION NOBODY HAD — a method the harness HAS and answers WRONGLY
#
# Requirement 1 covers ABSENCE: `st.balloons()` raises `HarnessGap` and says NOT A PAGE DEFECT.
# ⚠️ NOTHING ASKED WHETHER A METHOD THE HARNESS PROVIDES GIVES BACK WHAT STREAMLIT WOULD, and
# the answer was no in five places at once — every one of them reachable only through a column:
#
#     st.selectbox("Down", [...])  -> 'Any'      left.selectbox("Down", [...]) -> None
#     st.multiselect(…, default=…) -> ['a']      left.multiselect(…)           -> None
#     st.slider("S", value=3)      -> 3          left.slider("S", value=3)     -> None
#     st.expander("t")             -> Recorder   left.expander("t")            -> None
#     st.button("Go")              -> False      left.button("Go")             -> None
#
# `views/players.py:275` then runs `int(None)`, `states.section` catches it, and the page draws an
# Error card. A110 reported it as a page defect and A111 spent its round disproving it — the
# FOURTEENTH instance of R-571 and the fifth framing of "a harness gap looks like a page defect".
#
# ⚠️ THE NAMES ARE PARSED OUT OF THE STUB'S OWN SOURCE, never hand-written. `ci/check_health_
# signals.py` reads the emitter's valid values out of the model rather than restating them, for
# the reason this needs: a hand-written list covers the widgets somebody thought of, and the one
# that costs the next round is the one added after the list was written.

_HARNESS = ROOT / "tests" / "render_harness.py"

# The first probe the method accepts, tried in this order. Chosen against the MODULE stub and
# then replayed verbatim on the column, so a column that cannot take the same call fails here
# rather than being quietly probed with something easier.
_PROBES = (("Down", ["Any", "1", "2"]), (["Any", "1", "2"],), ("Down",), ())


def _names_the_stub_defines():
    """Every attribute `build()` sets on the stub, read out of `render_harness.py` by AST."""
    import ast
    source = _HARNESS.read_text()
    tree = ast.parse(source)
    build = next((node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "build"), None)
    assert build is not None, (
        "render_harness.build() no longer exists and this test is pinned to it by name")
    names = set()
    for node in ast.walk(build):
        # st.selectbox = lambda …
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "st"):
                    names.add(target.attr)
        # for name in _CONTAINERS: setattr(st, name, …)  — the list is read off the module, so
        # the three populations (PROVIDED, _FALSE_WIDGETS, _CONTAINERS) need no naming here.
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            sets_on_st = any(isinstance(inner, ast.Call)
                             and isinstance(inner.func, ast.Name)
                             and inner.func.id == "setattr"
                             for inner in ast.walk(node))
            listed = getattr(render_harness, node.iter.id, None)
            if sets_on_st and listed:
                names |= set(listed)
    return sorted(name for name in names if not name.startswith("__"))


def _shape(value):
    """What kind of answer this is, at the granularity two independent calls can agree on."""
    if isinstance(value, render_harness.Recorder):
        return "<Recorder>"
    if isinstance(value, (list, tuple)):
        return [_shape(item) for item in value]
    if callable(value):
        return "<callable>"
    return value


def test_the_ENUMERATION_of_stub_methods_cannot_go_blind():
    """🚨 A PARSER THAT RETURNS NOTHING PASSES EVERY ASSERTION BELOW IT.

    ⚠️ So the parsed list is checked against the stub OBJECT, not against a number. A widget
    added to `build()` in a shape this AST walk does not recognise fails HERE, on the commit that
    adds it, rather than silently dropping out of the delegation test — which is R-639's rule
    that a test which stops covering looks exactly like a test that passes.
    """
    st, _captured, _charts = render_harness.build()
    live = {name for name in vars(st) if not name.startswith("__")}
    parsed = set(_names_the_stub_defines())
    assert parsed == live, (
        f"the AST walk over `build()` and the stub it describes disagree. "
        f"Only in the source: {sorted(parsed - live)}. Only on the object: {sorted(live - parsed)}. "
        f"Whichever way round, the delegation test below has stopped covering those names.")
    for expected in ("selectbox", "radio", "multiselect", "button", "expander", "slider"):
        assert expected in parsed, f"{expected} is not in the enumeration and it is the defect class"


def test_a_COLUMN_answers_every_stub_METHOD_the_way_st_DOES():
    """🚨 THE ONE NOBODY WROTE. For every name the module-level stub defines, `st.columns()[0]`
    must give back what `st` gives back.

    ⚠️ IT IS NOT A TEST OF THE WIDGET LIST, IT IS A TEST OF THE SPLIT. `Recorder` delegates, so
    there is one definition per method and this asserts the delegation is actually wired — add a
    second definition to `Recorder` that drifts, or let one name fall back through
    `__getattr__`, and this goes red.
    """
    st, _captured, _charts = render_harness.build()
    column = st.columns(2)[0]
    for name in _names_the_stub_defines():
        target = getattr(st, name)
        if not callable(target):
            assert getattr(column, name) is target, (
                f"st.{name} is not callable, so a column must hand back THE SAME OBJECT — a "
                f"page that writes `st.session_state` through a column and reads it off `st` "
                f"otherwise loses the write. Got a different object.")
            continue
        probe = expected = None
        for candidate in _PROBES:
            try:
                expected = target(*candidate)
            except TypeError:
                continue
            probe = candidate
            break
        assert probe is not None, (
            f"no probe in {_PROBES!r} matches st.{name}'s signature — extend _PROBES rather "
            f"than skipping the name, because a name this test cannot call is a name it is not "
            f"covering")
        actual = getattr(column, name)(*probe)
        assert _shape(actual) == _shape(expected), (
            f"🚨 THE COLUMN AND THE MODULE STUB DISAGREE ABOUT st.{name}(). "
            f"st.{name}{probe!r} answered {expected!r} and a column answered {actual!r}. "
            f"A page that builds this control inside st.columns() gets the COLUMN's answer, and "
            f"a wrong answer arrives in the page as an exception inside `states.section`, which "
            f"catches it and draws an Error card — INDISTINGUISHABLE FROM A PAGE DEFECT. That is "
            f"R-617: it cost A110 a false finding and A111 a whole round. Fix it by making "
            f"`Recorder.__getattr__` delegate to the stub; do NOT add a second definition of "
            f"{name} to `Recorder`, because two definitions of one widget is what drifted.")


def test_a_COLUMN_records_the_control_AND_returns_its_value_both_not_either():
    """⚠️ BOTH, NOT EITHER. The delegation must not buy the right answer by dropping the record.

    Eight files assert on `.events` — "this sentence is a caption, not a heading", "the panel
    drew exactly two markdown blocks" — and a column whose `selectbox` returned `'Any'` and
    recorded nothing would take the guard off every control drawn in a column while leaving the
    suite green.
    """
    st, captured, _charts = render_harness.build()
    left, right = st.columns(2)
    value = left.selectbox("Down", ["Any", "1", "2"])
    assert value == "Any", "the answer"
    assert ("selectbox", "Down ['Any', '1', '2']") in captured.events, (
        f"the control returned its value and did not record that it was drawn: {captured.events}")
    assert any("Down" in entry for entry in captured), (
        "the flat list is what `render()` joins and `plain()` regexes — it must carry the draw too")
    # And the stub's own drawing methods must not be recorded TWICE by the delegation.
    right.markdown("one block")
    assert [body for kind, body in captured.events if kind == "markdown"] == ["one block"], (
        f"markdown was recorded more than once through a column: {captured.events}")


def test_an_UNPROVIDED_method_raises_LOUDLY_FROM_A_COLUMN_TOO():
    """⚠️ REQUIREMENT 1 COVERED `st`, AND A COLUMN SWALLOWED IT.

    `st.balloons()` has said NOT A PAGE DEFECT since A095; `left.balloons()` recorded the call
    and returned None, so the same absence was silent as soon as it happened inside a column —
    the same asymmetry as the wrong-answer defect, one layer along.
    """
    st, _captured, _charts = render_harness.build()
    column = st.columns(2)[0]
    with pytest.raises(render_harness.HarnessGap) as caught:
        column.balloons()
    assert "NOT A PAGE DEFECT" in str(caught.value)


def test_a_Recorder_built_WITHOUT_a_stub_keeps_the_old_behaviour():
    """§3 rule 3.1: the stub is an optional second argument and the default is what was there.

    `Recorder([])` is a live call site in this file and A's `test_export_page.py` rolls its own
    recorder entirely. A shared-module change ships the parameter and the default; it does not
    make the other session's call sites raise.
    """
    captured = []
    container = render_harness.Recorder(captured)
    assert container.balloons("anything") is None
    assert captured == ["anything"]


# --- ✅ R-617, PART 3: the test that could not be written before this round

def _drive_a_section_that_builds_controls_in_columns(rows):
    """Call `views.players._drill_down` — the real section, with a stubbed query.

    ⚠️ NOT `render_harness.render()`. That draws a whole page against LIVE serving, and the
    `flake8 + pytest` job has no database — A111 turned CI red once by calling it in a pytest and
    the convention it broke is the one every panel test in this suite already follows. `render()`
    is the session-level live tool §6 asks for in a report.

    ⚠️ AND IT IS A'S PAGE, READ AND NOT EDITED. `site/views/players.py` and
    `tests/test_players_page.py` are session A's; this drives A's section from B's file to prove
    what the harness can now do, and changes neither.
    """
    import importlib
    import pandas as pd
    with render_harness.streamlit_stubbed() as (_st, captured, _charts):
        players = importlib.reload(importlib.import_module("views.players"))
        players.query = lambda sql, params=None: pd.DataFrame(rows)
        players._drill_down(2026, "a-player-1")
        render_harness.assert_no_error_card(captured, "the players plays section")
        return "\n".join(captured)


def test_a_SECTION_THAT_BUILDS_CONTROLS_IN_COLUMNS_reaches_its_own_empty_state():
    """🚨 THE POINT OF THE WHOLE ROUND, AND IT IS A'S SECTION BECAUSE A'S SECTION IS WHAT BROKE.

    `views/players.py:254-258` builds three selectboxes on three columns and then runs
    `None if down == "Any" else int(down)`. Against the old Recorder that was `int(None)`, caught
    by `states.section`, drawn as an Error card — **on a page with no defect in it**. A110 filed
    it, Cowork registered it, A111 disproved it, and A's own test file carries a docstring saying
    the empty-plays assertion "cannot be written against the harness as it stands".

    ✅ IT CAN NOW, AND THIS IS IT: an empty frame reaches the section's OWN Empty state instead of
    a failure card. ⚠️ The claim is about the harness, not about the page — the page was always
    right, which is exactly what made the artifact expensive.
    """
    text = _drive_a_section_that_builds_controls_in_columns([])
    assert "cfdb-empty" in text, (
        "the section did not reach its Empty state. Before R-617 it could not: the filters it "
        "builds in columns answered None and the page raised int(None) first.")
    assert render_harness.ERROR_CARD not in text


def test_the_SAME_SECTION_renders_its_table_when_there_are_plays():
    """⚠️ AN EMPTY STATE ALONE DOES NOT PROVE THE CONTROLS ANSWERED.

    A section that raised and drew a card would fail the test above; a section whose filters
    answered `None` in some new way could still reach an Empty state by accident. So the
    populated path is asserted too — the play has to appear, which means all three filters
    resolved to 'Any' and the query ran unfiltered.
    """
    text = _drive_a_section_that_builds_controls_in_columns([{
        "play_id": 1, "season": 2026, "week": 3, "game_date": "2026-09-12",
        "player_slug": "a-player-1", "team": "Arizona State", "opponent": "Michigan",
        "stat_type": "rushing", "stat": "yards", "period": 2, "down": 2, "distance": 7,
        "down_distance_display": "2nd & 7", "distance_bucket": "medium",
        "field_zone": "own territory", "play_type": "Rush", "play_text": "run for 9 yards",
        "yards_gained": 9, "is_scoring_play": False, "ppa": 0.4, "as_of_ts": "2026-09-12",
    }])
    assert "2nd & 7" in text, f"the plays table did not render: {text[:400]}"
    assert render_harness.ERROR_CARD not in text
