r"""The gap between a card metric's number and its sparkbar — measured at the GLYPHS.

🚨 A216 PART 0 (cfdb-main-R-2604). Cowork, from A223's own after-crop enlarged: *"the bar's
rounded left end begins at or inside the right edge of the `0` in `170`. There is no gap at
all."* Both card shapes already carry a CSS `gap` — `.cfdb-card-metric` at .25rem and
`.cfdb-card-stat` at .35rem — so "no gap at all" is a claim about the RENDER, and the render is
where it has to be answered.

## WHY THE GLYPH AND NOT THE BOX, WHICH IS THE WHOLE POINT OF THIS SCRIPT

`.cfdb-card-value` is `flex:1 1 auto; text-align:right`, so its BOX right edge is always
exactly `gap` away from the spark. Measuring boxes would report the CSS back to itself and
could never see the defect. **What a reader sees is the last glyph's ink**, and a right-aligned
digit does not necessarily end at its box edge: a proportional or tabular font carries a right
side bearing, and `text-align:right` aligns the advance width, not the ink.

⚠️ AND THE TRACK IS NOT THE BAR. `.cfdb-card-spark` is the full-width TRACK (12% currentColor);
`.cfdb-card-spark > i` is the BAR (a share of it). They start at the same x only when the bar
fills the track. Both are reported, because Cowork's crop shows whichever is darker.

## Instrument failures this is built against

- **R-2455** — `innerText` is empty for anything not visible. `textContent` throughout.
- **A217's R-2623** — `Range.getClientRects()` returns a rect per FRAGMENT. The ink extent is
  the UNION of those rects, never one of them and never a count.
- **A210's R-2459** — a success-is-empty check must not gate what follows with `&&`.
- **A211's R-2506** — `color-scheme` lives on the app view container, not on `body`.

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_spark_gap.py light
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                                  # noqa: E402

WIDTHS = (1440, 1024)

MEASURE = r"""() => {
  const px = (v) => +(+v).toFixed(2);

  // The union of an element's text ink rects (A217's R-2623). Returns null when the element
  // holds no rendered text at all, which is a different answer from a zero-width box.
  const ink = (el) => {
    if (!el) return null;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let left = Infinity, right = -Infinity, n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) {
        if (!b.width || !b.height) continue;
        left = Math.min(left, b.left); right = Math.max(right, b.right);
      }
    }
    return right === -Infinity ? null : {left: px(left), right: px(right)};
  };

  const out = [];
  // Both card shapes. `.cfdb-card-metric` is the multi-metric cell (value + spark on the
  // FIRST metric only); `.cfdb-card-stat` is the single-metric board's cell.
  for (const sel of ['.cfdb-card-metric', '.cfdb-card-stat']) {
    for (const cell of document.querySelectorAll(sel)) {
      const value = cell.querySelector('.cfdb-card-value');
      const track = cell.querySelector('.cfdb-card-spark');
      if (!value || !track) continue;                 // a metric column with no bar
      const glyph = ink(value);
      if (!glyph) continue;
      const bar = track.querySelector('i');
      const tRect = track.getBoundingClientRect();
      const bRect = bar ? bar.getBoundingClientRect() : null;
      const vBox = value.getBoundingClientRect();
      // 🚨 WHICH NUMBER DOES THE BAR APPEAR TO BELONG TO? A216's second question, and it is
      // not answerable from the gap alone. The bar sits BETWEEN its own figure and the next
      // one, so it reads as belonging to whichever is closer. Measured ink-to-ink both ways.
      let toNext = null;
      const next = cell.nextElementSibling;
      if (next) {
        const nGlyph = ink(next.querySelector('.cfdb-card-value') || next);
        const rightEdge = bRect && bRect.width ? bRect.right : tRect.right;
        if (nGlyph) toNext = px(nGlyph.left - rightEdge);
      }
      out.push({
        to_next_glyph: toNext,
        shape: sel,
        text: value.textContent.trim(),
        digits: value.textContent.trim().replace(/[^0-9]/g, '').length,
        // the three readings that matter, in ascending strictness
        box_to_track: px(tRect.left - vBox.right),
        glyph_to_track: px(tRect.left - glyph.right),
        glyph_to_bar: bRect && bRect.width ? px(bRect.left - glyph.right) : null,
        track_w: px(tRect.width),
        bar_w: bRect ? px(bRect.width) : null,
      });
    }
  }
  return out;
}"""


def run(scheme: str = "light") -> list:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 1100},
                                      device_scale_factor=2, color_scheme=scheme)
            page = ctx.new_page()
            # ⚠️ `?tab=back` AND THE SCROLL ARE BOTH LOAD-BEARING, copied from
            # `ci/measure_card_budget.py` rather than reinvented: the boards live on Looking
            # Back, and Streamlit renders them lazily as the container scrolls. A run without
            # the scroll measures whatever happened to be in the first viewport.
            page.goto(f"http://localhost:8604{page_url('today')}?tab=back",
                      wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(9000)
            for _ in range(6):
                page.mouse.wheel(0, 18000)
                page.wait_for_timeout(1200)
            page.wait_for_timeout(2500)
            dialogs = page.locator('[role="dialog"]').count()
            if dialogs:
                raise SystemExit(f"{dialogs} Streamlit dialog(s) over the page — "
                                 "the route is wrong, not the measurement (ci/page_url.py)")
            for row in page.evaluate(MEASURE):
                row["width"] = width
                rows.append(row)
            ctx.close()
        browser.close()
    return rows


def summarise(rows: list) -> str:
    lines = []
    for width in WIDTHS:
        at = [r for r in rows if r["width"] == width]
        lines.append(f"\n=== {width}px — {len(at)} cells carrying a spark ===")
        if not at:
            lines.append("  none. A card shape changed, or the boards did not render.")
            continue
        lines.append(f"  {'shape':22}{'value':>8}{'box→track':>11}{'glyph→track':>13}"
                     f"{'glyph→bar':>11}")
        for shape in ('.cfdb-card-metric', '.cfdb-card-stat'):
            same = [r for r in at if r["shape"] == shape]
            if not same:
                continue
            # one line per distinct digit count, so a 3-digit and a 1-digit value are both seen
            seen = {}
            for r in same:
                seen.setdefault(r["digits"], r)
            for digits in sorted(seen):
                r = seen[digits]
                gb = "—" if r["glyph_to_bar"] is None else f'{r["glyph_to_bar"]:.2f}'
                lines.append(f"  {shape:22}{r['text']:>8}{r['box_to_track']:>11.2f}"
                             f"{r['glyph_to_track']:>13.2f}{gb:>11}")
            gaps = [r["glyph_to_track"] for r in same]
            lines.append(f"  {shape} — {len(same)} cells, "
                         f"glyph→track min {min(gaps):.2f} max {max(gaps):.2f}")
            bad = [r for r in same if r["glyph_to_track"] <= 0]
            lines.append(f"    cells with NO positive gap between the number and the bar:"
                         f" {len(bad)} of {len(same)}")
            pair = [r for r in same if r["to_next_glyph"] is not None]
            if pair:
                own = [r["glyph_to_track"] for r in pair]
                nxt = [r["to_next_glyph"] for r in pair]
                closer = sum(1 for r in pair
                             if r["glyph_to_track"] < r["to_next_glyph"])
                lines.append(f"    bar→its own number {min(own):.2f}–{max(own):.2f}px  vs  "
                             f"bar→the NEXT number {min(nxt):.2f}–{max(nxt):.2f}px")
                lines.append(f"    cells where the bar is CLOSER to its own number:"
                             f" {closer} of {len(pair)}")
    return "\n".join(lines)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    rows = run(scheme)
    print(f"scheme={scheme}")
    print(summarise(rows))
    Path("/tmp/spark_gap_%s.json" % scheme).write_text(json.dumps(rows, indent=1))
