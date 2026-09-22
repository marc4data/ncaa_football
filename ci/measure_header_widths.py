"""How wide must a table header be to draw on ONE line? Measured in a real browser.

🚨 THIS EXISTS BECAUSE A189's MEASUREMENT WAS WRONG IN A WAY THAT LOOKED RIGHT, AND THE TEST
BUILT ON IT THEN CERTIFIED THE DEFECT. A189 pinned Most Exciting's last six columns at
"the measured header plus 16px of padding" and asserted the widths against a hand-recorded
`header_px` table. Cowork then looked at A189's own renders and found `4TH / QTR` and
`HOW CLOSE, / LATE` wrapping onto two lines at both 1440 and 1100 — the exact defect the
round reported fixed, under a green test.

📊 WHY THE TWO DISAGREED, MEASURED RATHER THAN GUESSED. Three separate things, compounding:

    the canvas shorthand   A189 measured with `measureText` on `getComputedStyle(el).font`.
                           **That shorthand carries neither `text-transform` nor
                           `letter-spacing`**, and this header row has BOTH — the CSS is
                           `text-transform:uppercase; letter-spacing:.0208em`. So it measured
                           "4th qtr" where the browser draws "4TH QTR", tracked.
    the padding            recorded as 16px; the rule is `.4rem .55rem`, so **17.6px**.
    the sort glyph         `⇅` is a separate inline element inside the same `th`.

    4th qtr           A189 recorded 58px + 16 = 74px slot ...... browser needs 82.9px
    How close, late   A189 recorded 113px + 16 = 129px slot .... browser needs 145.0px

⚠️ AND READING THE LIVE HEADER'S BOX BACK DOES NOT FIX IT — which is the trap that cost this
round a measurement too. A `Range.getBoundingClientRect()` over a header that has ALREADY
WRAPPED returns the width of the wrapped box, which is the column's own width minus padding.
Every wrapped column duly reported `drawn == slot - 17.6`, six numbers that look like six
measurements and are really the layout read back to itself. **A wrapped element cannot tell
you how wide it wanted to be.**

✅ SO EACH HEADER IS CLONED INTO AN OFF-SCREEN TABLE WITH `white-space:nowrap` AND NO WIDTH
CONSTRAINT, AND THE BROWSER IS ASKED HOW WIDE IT CAME OUT. Nothing is reconstructed: the
transform, the tracking, both paddings, the sort glyph and the font fallback are all in the
number because the browser's own layout engine applied all of them. That is the difference
between measuring what the browser draws and modelling it.

⚠️ NOT PART OF THE TEST SUITE, DELIBERATELY — the same call `ci/measure_chart_heights.py`
makes, for the same reason. It needs Chromium and a live render, so making it a test would
mean a conditional skip, and a guard that skips itself is the failure mode this project has
spent a fortnight removing. **`tests/test_today_page.py` imports `HEADER_ONE_LINE_PX` from
here and asserts the shipped widths against it**, so the test and the instrument cannot drift
apart: the numbers have exactly one home, and `--check` is what re-proves them.

    python ci/measure_header_widths.py <rendered-page.html>            # print the table
    python ci/measure_header_widths.py <rendered-page.html> --check    # fail if any is stale
"""
import sys

# 📊 MEASURED BY THIS FILE'S OWN `measure()` IN HEADLESS CHROMIUM, 2026-09-21, against a live
# `today.body()` render of 2026 week 3 — identical at 1100px, 1440px and 1600px, because a
# one-line text width is a property of the text and not of the viewport.
#
# ⚠️ THE NUMBER IS THE WHOLE `th` BOX: glyphs + uppercase + tracking + sort glyph + BOTH
# paddings. It is not a text width to which padding is then added — that addition is the step
# A189 got wrong, so there is nothing here to add.
HEADER_ONE_LINE_PX = {
    "4th qtr": 82.9,
    "OT": 44.1,
    "Game": 59.7,
    "How close, late": 145.0,
    "Excitement": 106.2,
    "Commentary": 109.5,
}

# ⚠️ A SHIPPED WIDTH IS THE MEASUREMENT PLUS THIS, AND THE ALLOWANCE IS FOR SUB-PIXEL ROUNDING
# AND FONT HINTING, NOT FOR COMFORT. A slot equal to the measurement to one decimal place is a
# slot that wraps the day a browser rounds the other way. It is deliberately small: a generous
# cushion would hide the next mismeasurement exactly as the 16px padding hid this one.
SUBPIXEL_ALLOWANCE_PX = 2

_MEASURE = r"""() => {
  let table = null;
  for (const t of document.querySelectorAll('table')) {
    const hs = [...t.querySelectorAll(':scope > thead > tr > th')].map(x => x.innerText.trim());
    if (hs.some(h => h.toLowerCase().startsWith('how close'))) { table = t; break; }
  }
  if (!table) return {error: 'Most Exciting table not found in this page'};
  // ⚠️ `:scope > thead > tr > th` AND NOT `thead th`. The Scoreboard cell contains its own
  // TABLE, and a descendant selector reports that inner table's headers as this one's — which
  // is how a first attempt at this measurement came back with "4 OT F 1 2 3 4 F".
  const ths = [...table.querySelectorAll(':scope > thead > tr > th')];

  const host = document.createElement('div');
  host.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden';
  const probe = document.createElement('table');
  probe.className = table.className;
  probe.style.cssText = 'table-layout:auto;width:auto;border-collapse:collapse';
  const tr = document.createElement('tr');
  const thead = document.createElement('thead');
  thead.appendChild(tr); probe.appendChild(thead); host.appendChild(probe);
  document.body.appendChild(host);

  const out = [];
  for (const th of ths) {
    const clone = th.cloneNode(true);
    clone.style.whiteSpace = 'nowrap';
    clone.style.width = 'auto';
    tr.innerHTML = '';
    tr.appendChild(clone);
    out.push({
      label: th.innerText.trim().replace(/\s+/g, ' '),
      slot: +th.getBoundingClientRect().width.toFixed(1),
      need: +clone.getBoundingClientRect().width.toFixed(1),
    });
  }
  host.remove();
  return {headers: out};
}"""

# The label carries the sort glyph in the DOM; the Col label does not.
_SORT_GLYPHS = "⇅↑↓"


def _label(raw: str) -> str:
    return raw.rstrip(_SORT_GLYPHS).strip()


# 🚨 THE LOOKUP IS CASE-INSENSITIVE, BECAUSE `innerText` RETURNS WHAT IS DRAWN.
# `text-transform:uppercase` is the very thing that made A189's measurement wrong, and it
# also means the browser hands back `4TH QTR` where the `Col` label is `4th qtr`. The first
# run of `--check` matched exactly ONE header — `OT`, the only label uppercase in both — and
# reported nothing stale for the other five **because it never looked them up**.
# ⚠️ That is this round's own defect class, committed inside the tool built to fix it: a
# check that passes because it compared nothing.
def _recorded(label: str):
    for key, value in HEADER_ONE_LINE_PX.items():
        if key.casefold() == label.casefold():
            return key, value
    return None, None


def measure(page_path: str, widths=(1440, 1100, 1600)) -> dict:
    """{label: one-line width in px}, taken in Chromium at each viewport.

    ⚠️ SEVERAL VIEWPORTS ON PURPOSE. The number must come back identical at all of them — a
    one-line text width cannot depend on the viewport — and a disagreement means the probe is
    measuring the slot again rather than the requirement.
    """
    from pathlib import Path
    from playwright.sync_api import sync_playwright

    page_html = Path(page_path).read_text()
    per_width = {}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for width in widths:
            page = browser.new_page(viewport={"width": width, "height": 1200},
                                    color_scheme="light")
            page.set_content(page_html, wait_until="load")
            page.wait_for_timeout(600)
            result = page.evaluate(_MEASURE)
            if "error" in result:
                raise SystemExit(f"ci/measure_header_widths.py: {result['error']}")
            per_width[width] = {_label(h["label"]): (h["slot"], h["need"])
                                for h in result["headers"]}
            page.close()
        browser.close()

    first = per_width[widths[0]]
    for width in widths[1:]:
        for label, (_slot, need) in per_width[width].items():
            if abs(first[label][1] - need) > 0.5:
                raise SystemExit(
                    f"{label!r} needs {first[label][1]}px at {widths[0]} but {need}px at "
                    f"{width} — a one-line width cannot depend on the viewport, so this probe "
                    f"is reading a slot back rather than measuring a requirement")
    return per_width


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    page_path, check = argv[0], "--check" in argv[1:]
    per_width = measure(page_path)
    width = sorted(per_width)[0]
    stale, wrapping, matched = [], [], set()
    print(f"{'header':<18}{'slot':>8}{'needs':>8}{'recorded':>10}")
    for label, (slot, need) in per_width[width].items():
        key, recorded = _recorded(label)
        if key is not None:
            matched.add(key)
        flag = ""
        if slot + 0.5 < need:
            flag += "  ← WRAPS"
            wrapping.append(label)
        if recorded is not None and recorded + 0.5 < need:
            flag += "  ← RECORDED VALUE IS STALE"
            stale.append((label, recorded, need))
        print(f"{label:<18}{slot:>8}{need:>8}"
              f"{'—' if recorded is None else recorded:>10}{flag}")

    # ⚠️ AND AN UNMATCHED RECORDED KEY IS A FAILURE, NOT A SILENCE. If a label is renamed,
    # every assertion about it silently stops running — which is exactly how the case
    # mismatch above went unnoticed. The tool says so rather than printing a clean table.
    unmatched = sorted(set(HEADER_ONE_LINE_PX) - matched)
    if unmatched:
        print(f"\nRECORDED BUT NOT FOUND IN THE RENDERED HEADER ROW: {unmatched} — these "
              f"constants are asserting about nothing")

    if stale:
        print("\nHEADER_ONE_LINE_PX understates what this browser draws:")
        for label, recorded, need in stale:
            print(f"  {label!r}: recorded {recorded}, browser needs {need}")
    if wrapping:
        print(f"\nThese headers wrap at {width}px: {wrapping}")
    return 1 if check and (stale or wrapping or unmatched) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
