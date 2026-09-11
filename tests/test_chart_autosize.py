"""R-659 / R-603 — Streamlit decides the autosize, and it decides it AFTER altair is done.

🚨 FOUR ROUNDS OF ASSERTIONS PASSED OVER THIS. B084 checked the shared axes, B085 the
coordinate, B086 and A097 the point's position in the declared domain — and every one of them
read `chart.to_dict()`, where `autosize` does not appear, because Streamlit adds it in
`_prepare_vega_lite_spec` on the way out. **So every assertion here goes through that function.**

⚠️ `fit` makes `height` the OUTER BOX rather than the plot: the title, the axis labels, the
axis title, the legend and the padding all come out of it, and the y scale gets the remainder.
At 150px on Matchup there was nothing left (R-603).

A100 measured all three of this site's remaining Streamlit charts in a real browser. Re-run
`ci/measure_chart_heights.py` to reproduce the table; the numbers live in comments at each call
site. The conclusions those numbers support are what this file protects.
"""
import ast
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from streamlit.elements.vega_charts import _prepare_vega_lite_spec      # noqa: E402

from views import performance                                           # noqa: E402

VIEWS = ROOT / "site" / "views"

# Every Streamlit chart call on the site, and the height it asks for. ⚠️ WRITTEN OUT rather
# than discovered, because a census that derives its expectation from the thing it censuses
# cannot fail — A089 shipped one that could not.
KNOWN_CHART_CALLS = {
    ("today.py", "altair_chart"),
    ("movement.py", "line_chart"),
    ("performance.py", "altair_chart"),
    ("matchup.py", "altair_chart"),          # session B's, fixed by B087
}

# Below this, the furniture leaves no usable plot. Matchup asked for 150 and got almost
# nothing; the calibration curve asked for 260 and was drawn 126 before A100.
MINIMUM_DECLARED_HEIGHT = 120


def _chart_calls():
    """(file, method, height) for every st.*_chart call under site/views, by AST.

    ⚠️ AST RATHER THAN GREP — A091's lesson, after a source-scanning test failed on its own
    comment. A comment mentioning `st.line_chart` is not a call.
    """
    found = []
    for path in sorted(VIEWS.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            name = node.func.attr
            if not name.endswith("_chart") or name in ("vega_lite_chart",):
                continue
            height = None
            for kw in node.keywords:
                if kw.arg == "height":
                    height = kw.value.value if isinstance(kw.value, ast.Constant) else kw.value
            found.append((path.name, name, height, node.lineno))
    return found


def test_every_streamlit_chart_call_is_accounted_for():
    """🚨 A FOURTH CHART MUST NOT APPEAR UNMEASURED. That is how this defect lived.

    Cowork's census for A100 was a grep and missed nothing, but a grep is not a guard. If a
    new chart lands, this goes red and the measurement script is one line away.
    """
    seen = {(f, m) for f, m, _h, _ln in _chart_calls()}
    assert seen == KNOWN_CHART_CALLS, (
        f"the site's chart calls changed: {seen ^ KNOWN_CHART_CALLS}. Every Streamlit chart "
        f"gets `autosize: fit` unless it declares its own — measure it with "
        f"ci/measure_chart_heights.py before trusting its height.")


def test_no_chart_asks_for_a_height_that_leaves_no_plot():
    """A chart whose plot area cannot carry an axis should not render a confident flat line."""
    for name, method, height, lineno in _chart_calls():
        if height is None or not isinstance(height, int):
            continue
        assert height >= MINIMUM_DECLARED_HEIGHT, (
            f"{name}:{lineno} asks for height={height}. Under Streamlit's `autosize: fit` the "
            f"title, axis labels, axis title and padding come out of that number before the "
            f"plot gets any — at 150px on Matchup the y axis collapsed entirely (R-603).")


def test_the_calibration_chart_declares_its_own_autosize():
    """🚨 THE FIX, ASSERTED WHERE IT ACTUALLY TAKES EFFECT.

    Built through the page's own helper and then run through Streamlit's real
    `_prepare_vega_lite_spec`, because that function is the thing that would overwrite it.
    ⚠️ Asserting `chart.to_dict()` would pass with the bug present — which is precisely how
    four rounds missed R-603.
    """
    frame = pd.DataFrame(
        {"Model says": [0.1, 0.5, 0.9], "Actually happened": [0.2, 0.4, 0.95]},
        index=pd.Index(["0-10%", "40-50%", "90-100%"], name="segment_value"))

    # ⚠️ DELIBERATELY NOT `render_harness.streamlit_stubbed` HERE, AND THE REASON IS A BUG IT
    # CAUSES. That helper reloads `lib.query` on entry and again on exit, and
    # `importlib.reload` rebinds a module's globals IN PLACE — so `check_contract` starts
    # raising a NEW `QueryContractError` class while any test that imported the old one still
    # holds the old object. A100 reproduced it: adding a third harness-using file turned five
    # `test_site_foundation` cases red, all of which pass alone. Logged for its own round; this
    # test needs one function and a recorder, not a page render, so it simply does not go near
    # the hazard.
    charts = []

    class _Recorder:
        """Only what `_calibration_chart` touches."""

        @staticmethod
        def altair_chart(chart, **_kwargs):
            charts.append(chart.to_dict())

    original, performance.st = performance.st, _Recorder
    try:
        performance._calibration_chart(frame)
    finally:
        performance.st = original

    assert charts, "the calibration chart drew nothing"
    prepared = _prepare_vega_lite_spec(charts[0], True)
    assert prepared["autosize"] == {"type": "fit-x", "contains": "padding"}, (
        f"the calibration chart came out of Streamlit with autosize="
        f"{prepared.get('autosize')}. Under `fit` its plot is drawn 126px of the 260 asked "
        f"for at a 16px axis font and 48px at 28px — a calibration curve that cannot show a "
        f"deviation. R-659.")
    assert prepared["height"] == 260


def test_the_bump_chart_keeps_the_horizontal_labels_its_measurement_rests_on():
    """R-659: today.py is SQUEEZED AND DELIBERATELY NOT FIXED, and this is why that holds.

    🚨 A CONCLUSION OF "FINE" WITH NO TEST IS A CONCLUSION NOBODY CAN RE-CHECK. The
    measurement (388px drawn of 420 at a 10px axis font, 345 at 28px) is a near-constant loss
    rather than a proportional one, and the reason is that the x labels are horizontal — so
    their height does not grow with their length. `labelAngle=0` is that premise in the
    source. Rotate them and the calibration curve's cliff applies here too: re-measure with
    ci/measure_chart_heights.py before assuming it is still fine.
    """
    source = (VIEWS / "today.py").read_text()
    assert "alt.Axis(labelAngle=0)" in source, (
        "today.py's bump chart no longer pins its x labels horizontal. A100 concluded it "
        "degrades gracefully BECAUSE of that; rotated labels grow vertically and eat the "
        "plot — re-measure before trusting the 420.")
