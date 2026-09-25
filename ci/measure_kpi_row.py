r"""The KPI row's fit: every tile's width, the row's total, and its HEIGHT at each viewport.

🚨 A216 PART 4 (cfdb-main-R-2603). Seven tiles, three of them carrying a picture, above a
section that already has plenty.

⚠️ HEIGHT IS MEASURED, NOT ONLY WIDTH, AND THAT IS A209/A210's LESSON APPLIED SOMEWHERE NEW.
A summary ROW that becomes a summary BLOCK at 1024 has not overflowed — it has silently
changed shape, and every width reading stays inside its budget while it happens. **The test
is whether all seven tiles share one horizontal band.**

⚠️ AND THE ROW SCROLLS RATHER THAN WRAPS, by design: it sits in the site's shared
`.cfdb-scroll` wrapper (A208), so `scrollWidth > clientWidth` is the EXPECTED state at a
narrow viewport, not a defect. What would be a defect is a second row of tiles.

## Instrument failures this is built against

- **R-2455** — `innerText` is empty for anything not visible. `textContent` throughout.
- **A213's R-2546** — a rounding bucket reads a centring offset as a different line. Tiles are
  clustered into bands by vertical OVERLAP, never by a rounded `top`.
- **A210's R-2459** — a success-is-empty check must not gate what follows with `&&`.

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_kpi_row.py light
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                                  # noqa: E402

# A231: four widths, not two. Marc's v17 asks for the row to take the Most Exciting table's
# width, and a change that is right at 1440 and wrong at 1300 is a change nobody measured.
WIDTHS = (1600, 1440, 1300, 1024)

MEASURE = r"""() => {
  const px = (v) => +(+v).toFixed(2);

  // 🚨 A225 PART 2. THE INK, NOT THE BOX — and A216's own R-2606 is exactly why. That round
  // measured BOX edges on the player cards and could not see a value overlapping its
  // sparkbar, because every box edge was correct. A numeral's box is its line box; what a
  // reader sees start at a y is the GLYPH. Union of the text rects, never a count of them
  // (A217's R-2623).
  const ink = (el) => {
    if (!el) return null;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let top = Infinity, bottom = -Infinity, n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) {
        if (!b.width || !b.height) continue;
        top = Math.min(top, b.top); bottom = Math.max(bottom, b.bottom);
      }
    }
    return top === Infinity ? null : {top: px(top), bottom: px(bottom)};
  };

  const row = document.querySelector('.cfdb-kpirow');
  if (!row) return {found: false};
  const scroller = row.closest('.cfdb-scroll');
  const tiles = [...row.querySelectorAll('.cfdb-kpi')].map((t) => {
    const r = t.getBoundingClientRect();
    const label = t.querySelector('.cfdb-kpi-label');
    const value = t.querySelector('.cfdb-kpi-value');
    const sub   = t.querySelector('.cfdb-kpi-sub');
    const glyph = ink(value);
    const labelInk = ink(label);
    return {
      label: label ? label.textContent.trim() : '',
      value: value ? value.textContent.trim() : '',
      sub:   sub   ? sub.textContent.trim()   : '',
      w: px(r.width), h: px(r.height), top: px(r.top), bottom: px(r.bottom),
      // 🚨 A235 (cfdb-main-R-3034). BOTH SELECTORS, BECAUSE THE ROW CHANGED RENDERER AND THIS
      // COUNTER SILENTLY WENT TO ZERO. `thumbnail()` emits `.cfdb-dist`; `panel()` emits
      // `.cfdb-dist-panel`, which is NOT a `.cfdb-dist`. A235 moved the KPI row from the first
      // to the second and this line went on reporting `0 charts` for a row carrying three of
      // them — the measurement was taken, printed, and false. **R-859: a selector counts
      // elements matching that selector, never "charts"** — so it names every shape a chart can
      // arrive in, and a fifth entry point will break it loudly rather than read zero.
      charts: t.querySelectorAll('.cfdb-dist, .cfdb-dist-panel').length,
      // the numeral's own ink, which is what PART 2 is about
      valueInkTop: glyph ? glyph.top : null,
      valueInkBottom: glyph ? glyph.bottom : null,
      labelLines: label ? Math.round(label.getBoundingClientRect().height /
                    (parseFloat(getComputedStyle(label).lineHeight) || 1)) : null,
      // 🚨 A231. `labelLines` ABOVE DIVIDES THE BOX HEIGHT AND SO CAN ONLY EVER SAY "2"
      // WHILE `min-height:3.2em` IS ON THE RULE — it reported all seven labels as wrapping
      // when what it was seeing was the RESERVE that A225 added because one of them did.
      // A round asking "may the reserve go?" cannot use it: the instrument answers the
      // question the reserve already decided. **A box measurement reports the CSS back to
      // itself** (R-2606), and this is that, one level down from the numerals.
      //
      // ✅ THE TEXT'S OWN LINE BOXES. A Range over the label's contents yields ONE RECT PER
      // LINE the text actually occupies, so it is blind to the box the text sits in.
      labelTextLines: (() => {
        if (!label) return null;
        const rg = document.createRange();
        rg.selectNodeContents(label);
        const rects = [...rg.getClientRects()].filter((q) => q.width > 0 && q.height > 0);
        const tops = [];
        rects.forEach((q) => {
          if (!tops.some((y) => Math.abs(y - q.top) < 2)) tops.push(q.top);
        });
        return tops.length;
      })(),
      labelInkTop: labelInk ? labelInk.top : null,
      labelBoxH: label ? px(label.getBoundingClientRect().height) : null,
    };
  });
  // BANDS BY VERTICAL OVERLAP (A213's R-2546), never by a rounded `top`: a tile centred a
  // pixel differently is the same band, and a tile that wrapped is not.
  const bands = [];
  for (const t of tiles) {
    const band = bands.find((b) => t.top < b.bottom - 2 && t.bottom > b.top + 2);
    if (band) { band.top = Math.min(band.top, t.top);
                band.bottom = Math.max(band.bottom, t.bottom); band.n += 1; }
    else bands.push({top: t.top, bottom: t.bottom, n: 1});
  }
  const rowRect = row.getBoundingClientRect();
  return {
    found: true,
    tiles,
    bands: bands.length,
    rowW: px(rowRect.width), rowH: px(rowRect.height),
    scrollW: scroller ? px(scroller.scrollWidth) : null,
    clientW: scroller ? px(scroller.clientWidth) : null,
    scrolls: scroller ? scroller.scrollWidth > scroller.clientWidth + 1 : null,
    inScrollWrapper: !!scroller,
  };
}"""


def run(scheme: str = "light", week: str = "3") -> list:
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 1100},
                                      color_scheme=scheme, device_scale_factor=2)
            page = ctx.new_page()
            # 🚨 A235 (cfdb-main-R-3033). `networkidle` WAS A PROXY AND IT BOTH HANGS AND LIES.
            # It timed out at 120s on a page that had rendered correctly in under 10 — measured:
            # the same four widths loaded with `domcontentloaded` gave 7 tiles, 3 charts and 0
            # error cards every time, while `networkidle` never settled. ⚠️ AND IT WAS THE WEAKER
            # ASSERTION IN THE OTHER DIRECTION TOO: "no requests for 500ms" can be satisfied by a
            # page whose KPI row is absent, which is why `summarise` carries a `found: false`
            # branch at all. **Waiting for the element under measurement is both more reliable and
            # strictly stronger**, and the 9s settle that follows is unchanged — it is what lets
            # Streamlit finish its own re-run before anything is read.
            page.goto(f"http://localhost:8604{page_url('today')}?tab=back&week={week}",
                      wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector(".cfdb-kpirow", timeout=120000)
            page.wait_for_timeout(9000)
            data = page.evaluate(MEASURE)
            data.update({"width": width, "scheme": scheme, "week": week,
                         "dialogs": page.locator('[role="dialog"]').count()})
            out.append(data)
            ctx.close()
        browser.close()
    return out


def summarise(rows: list) -> str:
    lines = []
    for r in rows:
        lines.append(f"\n=== {r['width']} {r['scheme']} week={r['week']} "
                     f"— dialogs {r['dialogs']} ===")
        if not r.get("found"):
            lines.append("  🚨 NO `.cfdb-kpirow` ON THE PAGE. The panel did not render.")
            continue
        lines.append(f"  {'tile':30}{'w':>8}{'h':>8}{'charts':>8}  value / sub")
        for t in r["tiles"]:
            lines.append(f"  {t['label'][:29]:30}{t['w']:>8.1f}{t['h']:>8.1f}"
                         f"{t['charts']:>8}  {t['value']} | {t['sub']}")
        total = sum(t["w"] for t in r["tiles"])
        lines.append(f"  {len(r['tiles'])} tiles, widths total {total:.1f}px, "
                     f"row {r['rowW']:.1f} x {r['rowH']:.1f}px")
        lines.append(f"  inside .cfdb-scroll: {r['inScrollWrapper']} · "
                     f"scrollWidth {r['scrollW']} vs clientWidth {r['clientW']} "
                     f"-> scrolls: {r['scrolls']}")
        verdict = "✅ ONE BAND" if r["bands"] == 1 else f"🚨 {r['bands']} BANDS — the row wrapped"
        lines.append(f"  {verdict}")

        # 🚨 PART 2's ACCEPTANCE, AND IT IS THE SAME SHAPE AS A221's: the number of DISTINCT
        # top edges across the seven big numerals must be ONE. A216 measured the ROW — one
        # band, 110.0px — and that was correct and blind to this: the row is one band and the
        # FIGURES INSIDE IT were not on one line, because a label that wraps pushes its
        # numeral down.
        tops = [t["valueInkTop"] for t in r["tiles"] if t["valueInkTop"] is not None]
        distinct = sorted({round(v, 1) for v in tops})
        lines.append(f"  numeral ink tops: {distinct}")
        spread = (max(tops) - min(tops)) if tops else 0
        ok = "✅" if len(distinct) == 1 else "🚨"
        lines.append(f"  {ok} DISTINCT TOP EDGES ACROSS {len(tops)} NUMERALS: "
                     f"{len(distinct)} (spread {spread:.1f}px)")
        # 🚨 THE TEXT'S LINES, NOT THE BOX'S. See `labelTextLines` in MEASURE for why the
        # box-derived figure cannot answer this while the reserve exists.
        wrapped = [t["label"] for t in r["tiles"] if (t.get("labelTextLines") or 1) > 1]
        lines.append(f"  labels whose TEXT wraps: {wrapped or 'none'}")
        boxed = [t["label"] for t in r["tiles"] if (t["labelLines"] or 1) > 1]
        lines.append(f"  labels whose BOX is two lines tall: "
                     f"{'all ' + str(len(boxed)) if len(boxed) == len(r['tiles']) else boxed}"
                     f"  <- the reserve, not a wrap")
        boxes = sorted({t["labelBoxH"] for t in r["tiles"] if t["labelBoxH"] is not None})
        lines.append(f"  label box heights: {boxes}")
    return "\n".join(lines)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    week = sys.argv[2] if len(sys.argv) > 2 else "3"
    rows = run(scheme, week)
    print(f"scheme={scheme} week={week}")
    print(summarise(rows))
    Path(f"/tmp/kpi_row_{scheme}_{week}.json").write_text(json.dumps(rows, indent=1))
