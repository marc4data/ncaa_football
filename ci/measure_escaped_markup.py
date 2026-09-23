r"""Does any page render ESCAPED markup where a tag belongs? Measured in a real browser.

🚨 A219 (cfdb-main-R-2663). THIS CLASS IS INVISIBLE TO THE PYTHON SUITE AND ALWAYS WILL BE.
`st.markdown(..., unsafe_allow_html=True)` parses Markdown FIRST, and a blank line terminates a
raw HTML block: the parser closes the tag, injects a `<p>`, and **escapes everything after it**.
B148 shipped exactly that and 1,934 tests stayed green, because the suite asserts the markup as
a Python string and the string is well-formed at that moment. **The parse happens in the
frontend.**

✅ SO THE SIGNATURE IS `&lt;` WHERE A TAG BELONGS — literal `<` text drawn on the page — and it
is cheap to look for across a whole page. This is a SCRIPT and deliberately not a test: it needs
Chromium and a running app, and a guard that skips itself when its dependencies are missing is
the failure this project spent a fortnight removing.

## ⚠️ WHAT IT CANNOT SEE — an instrument's blind spot is part of its result

1. **A page it does not visit, and a state it does not reach.** It loads each page's default
   view. A tab, an expander or a filter combination that is never opened is never measured.
2. **A shattered string whose remainder contains no tag at all.** Both signatures need
   something to catch: escaped text needs a tag the sanitiser refuses inline, and the injected
   `<p>` needs to land inside one of our own containers. A blank line at the very END of a
   string, after the last closing tag, terminates nothing anyone can see.
3. **Whether the escaping was a DEFECT.** A page legitimately showing `<` as content — a data
   dictionary describing a comparison operator, say — reads identically. Hits are REPORTED for
   a human, and the expected count is zero, so any hit is worth a look.
4. **Anything Streamlit renders outside the app view container**, which is not walked.
5. **Anything inside `<style>`, `<script>`, `<title>` or `<head>`**, which is code rather than
   rendered markup — skipped deliberately, and the reason is measured: the first run of this
   script returned 36 hits and **every one was a CSS comment in `theme.py`** mentioning
   `<script>`, `<col>` or `<td>`. Counting those answered a different question (§2.4).

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_escaped_markup.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url, registered_keys                 # noqa: E402

WIDTH = 1440

# The signature: a text node that literally contains `<tag` or `</tag`, plus the `<p>` Markdown
# injects. `textContent` on purpose — `innerText` returns empty for anything not visible, which
# is R-2455, paid for by A209.
MEASURE = r"""() => {
  const host = document.querySelector('[data-testid="stAppViewContainer"]');
  if (!host) return {error: 'no app view container'};
  const TAGLIKE = /&lt;\/?[a-zA-Z][a-zA-Z0-9-]*|<\/?[a-zA-Z][a-zA-Z0-9-]*(?=[\s>])/;
  // 🚨 `<style>` AND `<script>` HOLD CODE, NOT RENDERED MARKUP, AND THE FIRST RUN OF THIS
  // SCRIPT REPORTED 36 HITS THAT WERE ALL `theme.py`'s OWN CSS COMMENTS — prose mentioning
  // `<script>`, `<col>`, `<td>` and `<table>`. **A reader never sees a stylesheet's text.**
  // Scoping to rendered content is what the question actually was; counting CSS comments
  // answered a different one (§2.4).
  const SKIP = new Set(['STYLE', 'SCRIPT', 'TITLE', 'HEAD', 'NOSCRIPT']);
  const inCode = (el) => {
    for (let e = el; e && e !== host; e = e.parentElement) {
      if (SKIP.has(e.tagName)) return true;
    }
    return false;
  };
  const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
  const hits = [];
  let n;
  while ((n = walker.nextNode())) {
    const t = n.textContent;
    if (!t || !t.includes('<')) continue;
    if (inCode(n.parentElement)) continue;
    // a TEXT node holding something that looks like a tag is markup that was escaped
    if (!TAGLIKE.test(t)) continue;
    const el = n.parentElement;
    hits.push({
      text: t.trim().slice(0, 90),
      parent: el ? el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : '') : '?',
    });
  }
  // 🚨 THE SECOND SIGNATURE, AND IT IS THE ONE THAT CATCHES B148's ACTUAL SHAPE. When a blank
  // line terminates a raw HTML block, Markdown wraps what follows in a `<p>`. **This site's
  // markup never emits a `<p>`** — verified with `git grep '<p[ >]'` across all 18 view
  // modules and `lib/`: the only two hits are comments in `matchup.py` describing this very
  // defect. So a `<p>` inside one of our own containers is Markdown's, not ours.
  //
  // ⚠️ THE FIRST VERSION OF THIS SCRIPT HAD ONLY THE ESCAPED-TEXT SIGNATURE AND THE
  // CALIBRATION CAUGHT IT: a blank line injected after `<div class='cfdb-daygroup'>` shattered
  // the DOM (10 elements' difference) and produced NO escaped `<` at all, because the
  // remainder was a bare closing tag the sanitiser passes through. **Escaping only happens for
  // tags the sanitiser refuses inline — SVG internals, as in B148's `<circle>`.** A detector
  // built on that alone would have reported zero on a broken page.
  const injected = [...host.querySelectorAll('[class^="cfdb-"] p, [class*=" cfdb-"] p, svg p')]
      .map(el => ({
        text: (el.textContent || '').trim().slice(0, 60),
        parent: el.parentElement
            ? el.parentElement.tagName.toLowerCase()
              + (el.parentElement.className ? '.' + String(el.parentElement.className).split(' ')[0] : '')
            : '?',
      }));
  return {
    hits,
    injected,
    textNodes: host.querySelectorAll('*').length,
    dialogs: document.querySelectorAll('[role="dialog"]').length,
  };
}"""


def run(keys, scheme: str = "light") -> list:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": WIDTH, "height": 1100},
                                  color_scheme=scheme)
        for key in keys:
            page = ctx.new_page()
            try:
                page.goto(f"http://localhost:8604{page_url(key)}",
                          wait_until="networkidle", timeout=120000)
                page.wait_for_timeout(6000)
                for _ in range(3):
                    page.mouse.wheel(0, 14000)
                    page.wait_for_timeout(900)
                page.wait_for_timeout(1200)
                data = page.evaluate(MEASURE)
            except Exception as exc:                               # noqa: BLE001
                # ⚠️ A FAILED PROBE IS A FAILURE, NEVER "not yet" (§4.7.3 rule 2).
                data = {"error": f"{type(exc).__name__}: {exc}"}
            data.update(page_key=key, scheme=scheme)
            rows.append(data)
            page.close()
        browser.close()
    return rows


def summarise(rows: list) -> str:
    out, total = [], 0
    for d in rows:
        if d.get("error"):
            out.append(f"  🚨 {d['page_key']:14} {d['scheme']:5} PROBE FAILED: {d['error']}")
            total += 1
            continue
        hits = d.get("hits", [])
        injected = d.get("injected", [])
        total += len(hits) + len(injected)
        flag = "🚨" if (hits or injected) else "  "
        out.append(f"  {flag} {d['page_key']:14} {d['scheme']:5} "
                   f"escaped {len(hits):>3}  injected <p> {len(injected):>3}   "
                   f"elements {d['textNodes']:>5}  dialogs {d['dialogs']}")
        for h in hits[:3]:
            out.append(f"        escaped in <{h['parent']}>  {h['text']!r}")
        for h in injected[:3]:
            out.append(f"        <p> inside <{h['parent']}>  {h['text']!r}")
    out.append(f"  TOTAL SHATTERED-MARKUP SIGNALS: {total}   (must be 0)")
    return "\n".join(out)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    keys = sys.argv[2:] or registered_keys()
    data = run(keys, scheme)
    print(summarise(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
