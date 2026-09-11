"""How tall is the plot Streamlit actually draws? Measured in a real browser.

🚨 THIS EXISTS BECAUSE A NUMBER FROM THE SPEC CANNOT SEE THE DEFECT. `_prepare_vega_lite_spec`
sets `autosize = {"type": "fit", "contains": "padding"}` on any spec that declares none, and
`fit` makes `height` the OUTER BOX rather than the plot — the title, the axis labels, the axis
title, the legend and the padding come out of it first. `chart.to_dict()` shows none of that,
which is how four rounds of assertions passed over R-603 while Matchup's charts collapsed.

⚠️ NOT PART OF THE TEST SUITE, DELIBERATELY. It needs Chromium and the Vega CDN, so making it
a test would mean a conditional skip — and a guard that skips itself is the failure mode this
project has spent a fortnight removing. `tests/test_chart_autosize.py` holds the assertions
that can be made deterministically; this reproduces the numbers behind them.

    python ci/measure_chart_heights.py            # the three site charts
    python ci/measure_chart_heights.py specs.json # any captured specs

"Larger font" is modelled as Vega's axis/title/legend font sizes, which is what a reader's
bigger base font actually changes about a chart's furniture.
"""
import json
import sys
from pathlib import Path

FONT_SIZES = (10, 13, 16, 20, 24, 28)

# Below this a plot cannot carry an axis and a trend at the same time; the
# calibration curve was drawn 48px at the top of this range before A100.
USABLE_PLOT_FLOOR = 120
CONTAINER_WIDTH = 700

_PAGE = """<!doctype html><html><head>
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
</head><body style="margin:0;background:#fff"><div id="v"></div></body></html>"""

# The plot height, straight from the Vega view — not inferred from the SVG box.
_MEASURE = """async ([spec, width]) => {
    document.getElementById('v').style.width = width + 'px';
    const result = await vegaEmbed('#v', spec, {actions: false});
    return result.view.signal('height');
}"""


def _with_font(spec: dict, size: int) -> dict:
    spec = dict(spec)
    spec["width"] = "container"
    config = dict(spec.get("config") or {})
    for key, extra in (("axis", 0), ("legend", 0), ("title", 4)):
        config[key] = {**(config.get(key) or {}),
                       "labelFontSize": size, "titleFontSize": size + 2,
                       **({"fontSize": size + extra} if key == "title" else {})}
    spec["config"] = config
    return spec


def measure(specs: dict) -> None:
    from playwright.sync_api import sync_playwright

    header = "".join(f"{size:>7d}px" for size in FONT_SIZES)
    print(f"{'chart':40s}{header}   asked   verdict")
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": CONTAINER_WIDTH + 60, "height": 900})
        for label, spec in specs.items():
            drawn = []
            for size in FONT_SIZES:
                page.set_content(_PAGE)
                page.wait_for_function("typeof vegaEmbed !== 'undefined'", timeout=30000)
                drawn.append(page.evaluate(_MEASURE, [_with_font(spec, size), CONTAINER_WIDTH]))
            asked = spec.get("height")
            # ⚠️ THE VERDICT IS ABOUT WHETHER THE PLOT STAYS USABLE, not about the slope
            # alone. A chart can shed pixels steadily and still have plenty left; what makes
            # R-603 a defect is the plot running out. The slope is reported because it says
            # WHY — furniture that scales with the font is what gets you there.
            slope = (drawn[0] - drawn[-1]) / (FONT_SIZES[-1] - FONT_SIZES[0])
            worst = min(drawn)
            verdict = (f"USABLE  (worst {worst}px, -{slope:.1f}px per font px)"
                       if worst >= USABLE_PLOT_FLOOR
                       else f"COLLAPSES (worst {worst}px, -{slope:.1f}px per font px)")
            cells = "".join(f"{value:>9d}" for value in drawn)
            print(f"{label[:38]:40s}{cells}{asked:>8}   {verdict}")
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        measure(json.loads(Path(sys.argv[1]).read_text()))
    else:
        print("Pass a JSON file of {label: vega-lite spec}. Capture the site's own specs with "
              "Streamlit's `_prepare_vega_lite_spec` so the autosize under test is the real "
              "one — see tests/test_chart_autosize.py for how the calibration chart is built.")
