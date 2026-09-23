"""How tall is a SLATE row, at every width? Measured in a real browser.

🚨 THIS EXISTS BECAUSE A209 MEASURED EVERYTHING EXCEPT THE THING THAT BROKE. It measured the
header/body left-edge offset (0.00px, correct), the table's overflow, which columns were drawn
and what the note said — and never measured how TALL a row became. Putting two columns away
**doubled the row pitch at 1280**, from 47.7px to 106.6px, and every instrument the round
owned said it was fine.

📊 THE MECHANISM, MEASURED RATHER THAN REASONED (A210, cfdb-main-R-2456): a collapsed cell is
`width:0;overflow:hidden;visibility:hidden`, which HIDES and CLIPS its text but does not stop
it being LAID OUT. In a zero-width box the text wraps as hard as it can, and the row grows to
the tallest wrapped cell:

    th3  O/U   3 line boxes   54.9px      <- the header's driver
    td3  56.0  4 line boxes   85.1px      <- the row's driver
    td4  71°F  2 line boxes   19.0px         `.cfdb-wx` is already `nowrap`

⚠️ NOT PART OF THE TEST SUITE, for the reason `ci/measure_chart_heights.py` gives: it needs
Chromium and a running app, so making it a test would mean a conditional skip, and a guard
that skips itself is the failure this project has spent a fortnight removing.
`tests/test_today_slate_narrow.py` holds the assertion that can be made without a browser —
that the collapse rule stops the wrap — and this reproduces the numbers behind it.

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_slate_rows.py                 # light
    python ci/measure_slate_rows.py dark            # or a theme

🚨 `textContent`, NEVER `innerText`. `innerText` returns EMPTY under `visibility:hidden`, which
is exactly the family of cell being measured — A209's own R-2455, found the hard way.
"""
import json
import sys

WIDTHS = (1440, 1280, 1180, 1100, 1024)
URL = "http://localhost:8604/?tab=forward"

MEASURE = r"""() => {
  const out = [];
  document.querySelectorAll('.cfdb-slate').forEach(section => {
    const note = section.querySelector('.cfdb-scrollnote');
    const putAway = note && note.querySelector('.cfdb-slate-putaway');
    const scroll = note && note.querySelector('.cfdb-scrollnote-scroll');
    const shown = el => el && getComputedStyle(el).display !== 'none';
    section.querySelectorAll('.cfdb-slate-block').forEach((block, bi) => {
      const box = block.closest('.cfdb-scroll');
      const table = block.querySelector('table');
      const boxRect = box.getBoundingClientRect();
      const rows = [...table.querySelectorAll('tbody tr')];
      const tops = rows.map(tr => tr.getBoundingClientRect().top);
      // PITCH is what a reader feels: how far apart consecutive rows sit.
      const pitch = tops.length > 1 ? +(tops[1] - tops[0]).toFixed(1)
                                    : +rows[0].getBoundingClientRect().height.toFixed(1);
      const ths = [...table.querySelectorAll('thead th')].map((th, i) => {
        const r = th.getBoundingClientRect();
        return {i, t: (th.textContent || '').trim().split('\n')[0].replace(/[⇅\s]+$/, '')
                     || '(axis)',
                w: +r.width.toFixed(1), left: +(r.left - boxRect.left).toFixed(1),
                drawn: r.width > 0.5 && getComputedStyle(th).visibility !== 'hidden'};
      });
      const tds = [...(rows[0] ? rows[0].querySelectorAll('td') : [])].map(td => ({
        left: +(td.getBoundingClientRect().left - boxRect.left).toFixed(1)}));
      let offset = 0;
      for (let i = 0; i < Math.min(ths.length, tds.length); i++) {
        offset = Math.max(offset, Math.abs(ths[i].left - tds[i].left));
      }
      out.push({
        block: bi,
        container: Math.round(boxRect.width),
        table: Math.round(table.getBoundingClientRect().width),
        overflow: Math.round(box.scrollWidth - box.clientWidth),
        rowPitch: pitch,
        rowHeight: +rows[0].getBoundingClientRect().height.toFixed(1),
        headerHeight: +table.querySelector('thead tr').getBoundingClientRect().height.toFixed(1),
        rows: rows.length,
        offset: +offset.toFixed(2),
        drawn: ths.filter(t => t.drawn).map(t => `${t.i}:${t.t}`),
        hidden: ths.filter(t => !t.drawn).map(t => `${t.i}:${t.t}`),
        note: shown(note) ? (note.textContent || '').replace(/\s+/g, ' ').trim() : null,
        putAwayShown: shown(putAway), scrollShown: shown(scroll),
      });
    });
  });
  return out;
}"""


def measure(scheme: str = "light", shot_prefix: str = "") -> list:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 1000},
                                      color_scheme=scheme, device_scale_factor=2)
            page = ctx.new_page()
            page.goto(URL, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(7000)
            for _ in range(3):
                page.mouse.wheel(0, 20000)
                page.wait_for_timeout(1300)
            page.wait_for_timeout(2000)
            body = page.inner_text("body")
            dialogs = page.locator('[role="dialog"], [data-testid="stDialog"]').count()
            for row in page.evaluate(MEASURE):
                row.update(width=width, scheme=scheme, dialogs=dialogs,
                           notFound="Page not found" in body)
                rows.append(row)
            if shot_prefix:
                from pathlib import Path
                out = Path("/Users/marcalexander/projects/ai_orchestrator_claude/"
                           "ncaa_football/claude_work/renders")
                out.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out / f"{shot_prefix}_{width}_{scheme}.png"),
                                full_page=True)
            ctx.close()
        browser.close()
    return rows


def table(rows: list) -> str:
    head = (f"{'w':>5} {'cont':>5} {'tbl':>5} {'over':>5} {'PITCH':>7} {'rowH':>6} "
            f"{'head':>6} {'off':>5} {'dlg':>4}  put away")
    lines = [head]
    for r in rows:
        lines.append(
            f"{r['width']:>5} {r['container']:>5} {r['table']:>5} {r['overflow']:>5} "
            f"{r['rowPitch']:>7} {r['rowHeight']:>6} {r['headerHeight']:>6} "
            f"{r['offset']:>5} {r['dialogs']:>4}  {','.join(r['hidden']) or '—'}")
    return "\n".join(lines)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    data = measure(scheme, prefix)
    print(table(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
