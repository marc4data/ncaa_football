"""Does any DATA CELL wrap onto a second line? Measured in a real browser, per column.

🚨 THIS EXISTS BECAUSE A FIGURE BROKEN ACROSS TWO LINES IS WORSE THAN A CLIPPED ONE. Clipped,
a reader knows something is missing. Broken, `51.5` reads as two numbers and the row still
looks complete — Schedule shipped that in the O/U column and nobody's instrument could see it.

🚨 A218 (cfdb-main-R-2642). IT COUNTED `td` AND NOT `th`, AND SO DID THE SCRIPT THAT PRODUCED
A217's RESULTS TABLE. Both walked `tbody tr` only, so A217 reported *"numeric cells clipped: 0"*
at 1440 while `SPREAD`'s own header was clipped to `SPRE…` at that very width. **A measurement
that silently excludes half its population is the class this project has paid for repeatedly**,
and this one excluded the header row. It now walks `thead th` and `tbody td` together and
reports them separately.

🚨 AND IT NOW TELLS A MID-TOKEN BREAK FROM A SPACE WRAP, which is the distinction the whole
fix turns on. `ESPN` broken after `ESP` and `Eastern Washington` wrapped after `Eastern` are
both "two lines" and only one of them is a defect. The discriminator is measured, not guessed:
the widest SPACE-SEPARATED TOKEN is measured with a span, and if that token is wider than the
cell's content box then the only way the text can occupy two lines is by breaking inside it.

📊 THE MEASUREMENT IS A LINE COUNT FROM HEIGHT, NOT FROM RECTS. ⚠️ `Range.getClientRects()`
returns a rect per FRAGMENT, not per line — it reported 3 rects for a 4-character cell (A217's
R-2623) — so the line count comes from the rendered height of the cell's contents divided by
its line-height, and the widths come from a measuring span.

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
  // one measuring span, reused: cheaper and identical metrics for every cell
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;left:-9999px;';
  const host = document.querySelector('[data-testid="stAppViewContainer"]') || document.body;
  host.appendChild(probe);
  const widthOf = (text, cell) => {
    const cs = getComputedStyle(cell);
    probe.style.font = cs.font;
    probe.style.letterSpacing = cs.letterSpacing;
    probe.style.textTransform = cs.textTransform;
    probe.textContent = text;
    return probe.getBoundingClientRect().width;
  };

  const out = [];
  document.querySelectorAll('table.cfdb-table').forEach((table, ti) => {
    const heads = [...table.querySelectorAll('thead th')];
    if (!heads.length) return;
    const labels = heads.map(th => (th.textContent || '').trim().split('\n')[0]
        .replace(/[\u21c5\s]+$/, '') || '(blank)');
    const lineH = parseFloat(getComputedStyle(table).lineHeight) || 18;
    const cols = labels.map(l => ({label: l, numeric: false,
        thSplit: 0, thWrap: 0, thClip: 0, tdSplit: 0, tdWrap: 0, tdClip: 0,
        cells: 0, worstSplit: '', worstClip: ''}));

    const look = (cell, i, isHeader) => {
      if (!cols[i]) return;
      // 🚨 textContent: innerText is EMPTY under visibility:hidden (R-2455)
      const text = (cell.textContent || '').trim();
      if (!text) return;
      if (!isHeader) cols[i].cells += 1;
      cols[i].numeric = cols[i].numeric || cell.classList.contains('cfdb-num');
      const cs = getComputedStyle(cell);
      const box = cell.getBoundingClientRect().width
          - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      // 🚨 TOKENS COME FROM EACH TEXT NODE, NOT FROM THE CELL'S `textContent`. A team cell
      // is `<span>Massachusetts</span><span>3-0</span>` with no whitespace between them, so
      // the cell's textContent reads `Massachusetts3-0` — ONE token to a naive split, and the
      // instrument reported 4 mid-word splits in the Home column that were really the
      // designed break BETWEEN two elements. A break at an element boundary is not a broken
      // word.
      let widest = 0, widestTok = '';
      const tokWalker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
      let tokNode;
      while ((tokNode = tokWalker.nextNode())) {
        for (const tok of (tokNode.textContent || '').trim().split(/\s+/)) {
          if (!tok) continue;
          const w = widthOf(tok, tokNode.parentElement || cell);
          if (w > widest) { widest = w; widestTok = tok; }
        }
      }
      // 🚨 THE TEXT'S OWN HEIGHT, NOT THE CELL'S. `.cfdb-table td a.cfdb-cell-link` is
      // `display:block`, so a Range over the CELL measures the anchor — which fills the row.
      // The first run of this version reported 71 split `56.5` cells at 1280 on a column
      // `white-space:nowrap` makes unwrappable: it was reading the ROW's height, tall because
      // the team cells beside it wrap. ⚠️ And the count is taken from the union HEIGHT of the
      // text nodes, not from the number of rects — `getClientRects()` returns a rect per
      // FRAGMENT (A217's R-2623).
      const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
      let top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity, node;
      while ((node = walker.nextNode())) {
        if (!node.textContent.trim()) continue;
        const tr = document.createRange();
        tr.selectNodeContents(node);
        for (const rect of tr.getClientRects()) {
          if (rect.height === 0) continue;
          top = Math.min(top, rect.top);
          bottom = Math.max(bottom, rect.bottom);
          left = Math.min(left, rect.left);
          right = Math.max(right, rect.right);
        }
      }
      const lines = top === Infinity ? 1 : Math.max(1, Math.round((bottom - top) / lineH));
      // 🚨 THE CLIP TEST USES RENDERED GEOMETRY, NOT THE PROBE. A first version asked the
      // probe how wide the cell's TEXT would be and reported 70 clipped `Wx` cells at 1440 —
      // a column that wraps at its own space and clips nothing. The cell carries a weather
      // GLYPH the probe cannot reproduce, so its answer was about a string the browser never
      // draws. The laid-out text's own rects are the honest width.
      const drawnWidth = left === Infinity ? 0 : right - left;
      const tokenTooWide = widest > box + 1;
      if (lines > 1 && tokenTooWide) {
        // two lines AND no token fits: the only way is a break inside one
        if (isHeader) cols[i].thSplit += 1; else cols[i].tdSplit += 1;
        if (!cols[i].worstSplit) cols[i].worstSplit = widestTok.slice(0, 18);
      } else if (lines > 1) {
        if (isHeader) cols[i].thWrap += 1; else cols[i].tdWrap += 1;
      }
      if (lines <= 1 && drawnWidth > box + 1) {
        // one line and wider than the box: it is being clipped (ellipsis)
        if (isHeader) cols[i].thClip += 1; else cols[i].tdClip += 1;
        if (!cols[i].worstClip) cols[i].worstClip = text.slice(0, 18);
      }
    };

    heads.forEach((th, i) => look(th, i, true));
    table.querySelectorAll('tbody tr').forEach(tr =>
        [...tr.children].forEach((td, i) => look(td, i, false)));
    out.push({table: ti, rows: table.querySelectorAll('tbody tr').length, cols});
  });
  probe.remove();
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
        tally = {k: sum(c[k] for c in block["cols"])
                 for k in ("thSplit", "tdSplit", "thWrap", "tdWrap", "thClip", "tdClip")}
        lines.append(
            f"  {block['page']:<11} {block['width']:>5} {block['scheme']:<6} t{block['table']} "
            f"rows {block['rows']:>3} | SPLIT th {tally['thSplit']:>2} td {tally['tdSplit']:>4}"
            f" | wrap th {tally['thWrap']:>2} td {tally['tdWrap']:>4}"
            f" | clip th {tally['thClip']:>2} td {tally['tdClip']:>4}"
            f" | dialogs {block['dialogs']}")
        for c in block["cols"]:
            if c["thSplit"] or c["tdSplit"] or c["thClip"]:
                lines.append(
                    f"        {c['label']:<11} {'num' if c['numeric'] else 'txt'} "
                    f"split th {c['thSplit']} td {c['tdSplit']:>3} "
                    f"clip th {c['thClip']} td {c['tdClip']:>3}"
                    + (f"  worst split {c['worstSplit']!r}" if c["worstSplit"] else "")
                    + (f"  worst clip {c['worstClip']!r}" if c["worstClip"] else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "schedule"
    scheme = sys.argv[2] if len(sys.argv) > 2 else "light"
    prefix = sys.argv[3] if len(sys.argv) > 3 else ""
    data = measure(key, scheme, prefix)
    print(summarise(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
