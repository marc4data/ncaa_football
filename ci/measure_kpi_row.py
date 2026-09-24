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

WIDTHS = (1440, 1024)

MEASURE = r"""() => {
  const px = (v) => +(+v).toFixed(2);
  const row = document.querySelector('.cfdb-kpirow');
  if (!row) return {found: false};
  const scroller = row.closest('.cfdb-scroll');
  const tiles = [...row.querySelectorAll('.cfdb-kpi')].map((t) => {
    const r = t.getBoundingClientRect();
    const label = t.querySelector('.cfdb-kpi-label');
    const value = t.querySelector('.cfdb-kpi-value');
    const sub   = t.querySelector('.cfdb-kpi-sub');
    return {
      label: label ? label.textContent.trim() : '',
      value: value ? value.textContent.trim() : '',
      sub:   sub   ? sub.textContent.trim()   : '',
      w: px(r.width), h: px(r.height), top: px(r.top), bottom: px(r.bottom),
      charts: t.querySelectorAll('.cfdb-dist').length,
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
            page.goto(f"http://localhost:8604{page_url('today')}?tab=back&week={week}",
                      wait_until="networkidle", timeout=120000)
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
    return "\n".join(lines)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    week = sys.argv[2] if len(sys.argv) > 2 else "3"
    rows = run(scheme, week)
    print(f"scheme={scheme} week={week}")
    print(summarise(rows))
    Path(f"/tmp/kpi_row_{scheme}_{week}.json").write_text(json.dumps(rows, indent=1))
