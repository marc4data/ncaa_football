"""Does any DATA CELL wrap onto a second line? Measured in a real browser, per column.

🚨 THIS EXISTS BECAUSE A FIGURE BROKEN ACROSS TWO LINES IS WORSE THAN A CLIPPED ONE. Clipped,
a reader knows something is missing. Broken, `51.5` reads as two numbers and the row still
looks complete — Schedule shipped that in the O/U column and nobody's instrument could see it.

📊 THE MEASUREMENT IS A LINE-BOX COUNT, NOT AN EYE. A `Range` over a cell's contents returns
one client rect per rendered line, so a value on two lines reports 2. That is the count the
acceptance is written against, and it is zero for data cells.

⚠️ `textContent`, NEVER `innerText` — `innerText` is empty under `visibility:hidden`, and this
site collapses cells that way (A209's R-2455, A210's subject).

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_cell_wrap.py schedule          # a page key, or `/` for the default
    python ci/measure_cell_wrap.py schedule dark
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                              # noqa: E402

WIDTHS = (1440, 1280, 1100, 1024)

MEASURE = r"""() => {
  const out = [];
  document.querySelectorAll('table.cfdb-table').forEach((table, ti) => {
    const heads = [...table.querySelectorAll('thead th')];
    if (!heads.length) return;
    const cols = heads.map((th, i) => {
      const colEl = table.querySelectorAll('colgroup col')[i];
      const r = th.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(th);
      return {
        i,
        label: (th.textContent || '').trim().split('\n')[0].replace(/[⇅\s]+$/, '')
               || '(blank)',
        declared: colEl ? (colEl.style.width || getComputedStyle(colEl).width) : null,
        drawn: +r.width.toFixed(1),
        headerLines: range.getClientRects().length,
        // the widest a cell in this column WANTS to be, unwrapped
        minContent: 0, worstLines: 0, worstText: '', wrapped: 0, cells: 0,
      };
    });
    table.querySelectorAll('tbody tr').forEach(tr => {
      [...tr.children].forEach((td, i) => {
        if (!cols[i]) return;
        const text = (td.textContent || '').trim();
        cols[i].cells += 1;
        if (!text) return;
        const range = document.createRange();
        range.selectNodeContents(td);
        const lines = range.getClientRects().length;
        // 🚨 A CELL WHOSE CONTENT IS A BLOCK (a scoreboard, a strip of glyphs) legitimately
        // occupies several rects. Only count a cell whose TEXT is broken: measure the text
        // node runs, which is what a split number actually is.
        let textLines = 0;
        const walker = document.createTreeWalker(td, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
          if (!node.textContent.trim()) continue;
          const r2 = document.createRange();
          r2.selectNodeContents(node);
          textLines = Math.max(textLines, r2.getClientRects().length);
        }
        if (textLines > cols[i].worstLines) {
          cols[i].worstLines = textLines;
          cols[i].worstText = text.slice(0, 22);
        }
        if (textLines > 1) cols[i].wrapped += 1;
        void lines;
      });
    });
    out.push({table: ti, rows: table.querySelectorAll('tbody tr').length, cols});
  });
  return out;
}"""


def measure(page_key: str, scheme: str = "light", shot_prefix: str = "") -> list:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 1000},
                                      color_scheme=scheme, device_scale_factor=2)
            page = ctx.new_page()
            page.goto(f"http://localhost:8604{page_url(page_key)}",
                      wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(7000)
            for _ in range(3):
                page.mouse.wheel(0, 20000)
                page.wait_for_timeout(1200)
            page.wait_for_timeout(1500)
            dialogs = page.locator('[role="dialog"], [data-testid="stDialog"]').count()
            for block in page.evaluate(MEASURE):
                block.update(width=width, scheme=scheme, page=page_key, dialogs=dialogs)
                rows.append(block)
            if shot_prefix:
                out = Path("/Users/marcalexander/projects/ai_orchestrator_claude/"
                           "ncaa_football/claude_work/renders")
                out.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(out / f"{shot_prefix}_{page_key}_{width}_{scheme}.png"),
                    full_page=True)
            ctx.close()
        browser.close()
    return rows


def summarise(rows: list) -> str:
    lines = []
    for block in rows:
        bad = [c for c in block["cols"] if c["wrapped"]]
        head = [c for c in block["cols"] if c["headerLines"] > 1]
        lines.append(f"  {block['page']:<10} {block['width']:>5} {block['scheme']:<6} "
                     f"table {block['table']} rows {block['rows']:>3}  "
                     f"WRAPPED DATA CELLS: {sum(c['wrapped'] for c in block['cols']):>3}  "
                     f"wrapped headers: {len(head)}  dialogs {block['dialogs']}")
        for c in bad:
            lines.append(f"        {c['label']:<12} declared {str(c['declared']):>8} "
                         f"drawn {c['drawn']:>6}  {c['wrapped']}/{c['cells']} cells on "
                         f"{c['worstLines']} lines  worst={c['worstText']!r}")
        for c in head:
            lines.append(f"        header {c['label']:<10} on {c['headerLines']} lines "
                         f"(drawn {c['drawn']})")
    return "\n".join(lines)


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "schedule"
    scheme = sys.argv[2] if len(sys.argv) > 2 else "light"
    prefix = sys.argv[3] if len(sys.argv) > 3 else ""
    data = measure(key, scheme, prefix)
    print(summarise(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
