r"""The leaderboard card's budget: every slot, every metric's left edge, and the white space.

🚨 A221. Marc: *"Why are we trying to scrunch so much into such a tiny space? Why aren't they
numbers vertically aligned in the same space? Look at all the white space next to it!!!"*

**"Vertically aligned" IS A NUMBER, and this is the instrument that says it:** for each metric
column, how many DISTINCT LEFT EDGES the ten values have. **One is aligned. Ten is a ragged
edge.** A212 measured the card's slot widths and redistributed 5.5px inside them; it never asked
how many x-positions the values were starting from.

⚠️ SEPARATE FROM `ci/measure_player_cards.py` ON PURPOSE, AND THE REASON IS NOT SIZE. That script
answers *does a ranked card wrap* — a question about BANDS, with a band counter and a crop path
built for it. This answers *where does every number start* — a question about X-POSITIONS across
cards. Folding the second into the first would give one script two subjects and one summary
table that serves neither.

## The instrument failures this one is built against

- **R-2455** — `innerText` is empty for anything not visible. `textContent` throughout.
- **A191/A212's trap** — a `Range` over a box that has ALREADY WRAPPED returns the wrapped box.
  Every "how wide does this text want to be" reading clones into an off-screen `nowrap` probe.
- **A217's R-2623** — `Range.getClientRects()` returns a rect per FRAGMENT, not per line. Text
  extents are taken as the union of those rects, never as a count of them.
- **A213's R-2546** — a rounding bucket reads a centring offset as a different line. Lines are
  clustered by vertical OVERLAP.

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_card_budget.py light
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                                  # noqa: E402

WIDTHS = (1440, 1024)

MEASURE = r"""() => {
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;left:-9999px;';
  // 🚨 THE APP CONTAINER, NOT `document.body` — Streamlit sets `color-scheme` there, and a
  // probe on the body reads the LIGHT value in both themes (A211's R-2506).
  const host = document.querySelector('[data-testid="stAppViewContainer"]') || document.body;
  host.appendChild(probe);

  const px = (v) => +(+v).toFixed(2);
  const rect = (el) => el ? el.getBoundingClientRect() : null;
  const w = (el) => el ? px(el.getBoundingClientRect().width) : null;

  // the union of a node's text rects — never a count of them (A217's R-2623)
  const textExtent = (el) => {
    if (!el) return null;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity, n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) {
        if (!b.width || !b.height) continue;
        left = Math.min(left, b.left); right = Math.max(right, b.right);
        top = Math.min(top, b.top);   bottom = Math.max(bottom, b.bottom);
      }
    }
    return left === Infinity ? null
         : {left: px(left), right: px(right), top: px(top), bottom: px(bottom)};
  };

  const overlapsVertically = (a, b) =>
    a && b && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;

  const boards = [...document.querySelectorAll('.cfdb-cardboard')];
  const out = boards.map((board, bi) => {
    const heads = [...board.querySelectorAll('.cfdb-cardcol-head')].map(h => ({
      text: (h.textContent || '').replace(/\s+/g, ' ').trim(),
      left: px(h.getBoundingClientRect().left),
      right: px(h.getBoundingClientRect().right),
      // the hoisted metric names, and where each one actually sits
      names: [...h.querySelectorAll('.cfdb-cardcol-metrics')].map(s => ({
        text: (s.textContent || '').trim(),
        left: px(s.getBoundingClientRect().left),
        right: px(s.getBoundingClientRect().right)}))}));

    const cards = [...board.querySelectorAll('.cfdb-card')];
    // one COLUMN of the grid = every Nth card. The board is a flat list of cells, so the
    // column a card belongs to is its index modulo the number of headings.
    const ncols = Math.max(1, heads.length);

    const slots = [], valueEdges = {}, gaps = [], jersey = {beside: 0, above: 0, none: 0};
    const teamBlocks = [];
    let primaries = {};

    cards.forEach((card, ci) => {
      const col = ci % ncols;
      const team = card.querySelector('.cfdb-card-team');
      const who = card.querySelector('.cfdb-card-who');
      const mets = card.querySelector('.cfdb-card-metrics, .cfdb-card-stat');
      if (slots.length < ncols && team && who && mets) {
        const cs = getComputedStyle(card);
        slots.push({col, card: w(card),
          padding: px(parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)),
          team: w(team), who: w(who), metrics: w(mets),
          metricsLeft: px(rect(mets).left), cardRight: px(rect(card).right),
          cells: [...mets.querySelectorAll('.cfdb-card-metric')].map(w)});
      }

      // 🚨 PART 0 ITEM 2 — the left edge of every metric VALUE, per column
      const vals = [...card.querySelectorAll('.cfdb-card-value')];
      vals.forEach((v, vi) => {
        const key = col + ':' + vi;
        (valueEdges[key] = valueEdges[key] || []).push(px(rect(v).left));
      });

      // the primary (ranking) metric's value, for PART 2's spread table
      if (vals.length) {
        const t = (vals[0].textContent || '').replace(/[, ]/g, '');
        const num = parseFloat(t);
        if (!Number.isNaN(num)) (primaries[col] = primaries[col] || []).push(num);
      }

      // 🚨 PART 0 ITEM 3 — the white space Marc boxed: end of the NAME to start of the metrics
      const nameExt = textExtent(card.querySelector('.cfdb-player-name'));
      if (nameExt && mets) gaps.push({col, gap: px(rect(mets).left - nameExt.right)});

      // PART 4 — is the jersey beside the name, or above it?
      const jEl = card.querySelector('.cfdb-player-jersey');
      const nEl = card.querySelector('.cfdb-player-name');
      const jExt = textExtent(jEl), nExt = textExtent(nEl);
      if (!jExt) jersey.none += 1;
      else if (overlapsVertically(jExt, nExt)) jersey.beside += 1;
      else jersey.above += 1;

      // PART 3 — where the rank sits relative to the logo and the abbreviation
      if (team) {
        const logo = team.querySelector('.cfdb-logo-box, .cfdb-monogram-empty');
        const badge = team.querySelector('.cfdb-rank');
        const abbr = team.querySelector('.cfdb-team');
        // 🚨 A223 (cfdb-main-R-2626). THE PAINTED BOX, NOT THE BLOCK.
        // A221 measured the team BLOCK at 57.59 x 33.19 and called it correct. The block WAS
        // correct; the disc inside it was a 57.6 x 18 grey pill, because `flex-basis:100%`
        // landed on `.cfdb-logo-box` — which carries `border-radius:50%` and a background.
        // **A square box is the test.**
        const painted = logo ? logo.getBoundingClientRect() : null;
        const img = team.querySelector('.cfdb-logo');
        const imgBox = img ? img.getBoundingClientRect() : null;
        teamBlocks.push({
          ranked: !!badge,
          logoClass: logo ? logo.className : null,
          paintedW: painted ? px(painted.width) : null,
          paintedH: painted ? px(painted.height) : null,
          square: painted ? Math.abs(painted.width - painted.height) < 1.5 : null,
          imgW: imgBox ? px(imgBox.width) : null,
          imgH: imgBox ? px(imgBox.height) : null,
          radius: logo ? getComputedStyle(logo).borderTopLeftRadius : null,
          h: w(team) === null ? null : px(rect(team).height),
          width: w(team),
          rankWithLogo: !!(badge && logo && overlapsVertically(rect(badge), rect(logo))),
          rankWithAbbr: !!(badge && abbr && overlapsVertically(rect(badge), rect(abbr))),
          rankUnderlined: badge
            ? getComputedStyle(badge).textDecorationLine.includes('underline')
              || !!badge.closest('a')
            : null,
        });
      }
    });

    const edgeSummary = Object.entries(valueEdges).map(([k, v]) => {
      const [col, idx] = k.split(':').map(Number);
      const distinct = [...new Set(v.map(x => Math.round(x * 2) / 2))];
      return {col, idx, n: v.length, distinct: distinct.length,
              spread: v.length ? px(Math.max(...v) - Math.min(...v)) : 0};
    }).sort((a, b) => a.col - b.col || a.idx - b.idx);

    const spread = Object.entries(primaries).map(([col, vals]) => {
      const mx = Math.max(...vals), mn = Math.min(...vals);
      // 🚨 DISTINCT VALUES AS WELL AS THE RATIO. A bar can only show as many lengths as the
      // column has distinct numbers: ten cards all reading `4` draw ten identical bars however
      // wide the spread between 4 and 5 looks as a ratio.
      const distinct = [...new Set(vals)].sort((a, b) => b - a);
      return {col: +col, n: vals.length, max: mx, min: mn,
              ratio: mx ? +(mn / mx).toFixed(3) : null,
              distinct: distinct.length, values: distinct};
    }).sort((a, b) => a.col - b.col);

    const cardHeights = cards.map(c => px(rect(c).height));
    probe.remove();
    return {board: bi, cards: cards.length, heads, slots, edges: edgeSummary,
            gaps, jersey, spread,
            cardHeight: cardHeights.length
              ? {min: Math.min(...cardHeights), max: Math.max(...cardHeights)} : null,
            teamRanked: teamBlocks.filter(t => t.ranked),
            teamAllSquare: teamBlocks.filter(t => t.square).length,
            teamAllCount: teamBlocks.length,
            monogramCount: teamBlocks.filter(
              t => (t.logoClass || '').indexOf('monogram') >= 0).length,
            teamUnranked: teamBlocks.filter(t => !t.ranked).slice(0, 3)};
  });
  return out;
}"""


def run(scheme: str = "light") -> list:
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 1100},
                                      color_scheme=scheme, device_scale_factor=2)
            page = ctx.new_page()
            page.goto(f"http://localhost:8604{page_url('today')}?tab=back",
                      wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(9000)
            for _ in range(6):
                page.mouse.wheel(0, 18000)
                page.wait_for_timeout(1200)
            page.wait_for_timeout(2500)
            boards = page.evaluate(MEASURE)
            rows.append({"width": width, "scheme": scheme, "boards": boards,
                         "dialogs": page.locator('[role="dialog"]').count()})
            ctx.close()
        browser.close()
    return rows


BOARD_NAMES = {0: "Player yardage", 1: "Touchdowns", 2: "Defensive leaders"}


def summarise(rows: list) -> str:
    out = []
    for d in rows:
        out.append(f"=== {d['width']} {d['scheme']} — {len(d['boards'])} boards, "
                   f"dialogs {d['dialogs']} ===")
        for b in d["boards"]:
            name = BOARD_NAMES.get(b["board"], f"board {b['board']}")
            out.append(f"  {name}: {b['cards']} cards, "
                       f"card height {b['cardHeight']}")
            for h in b["heads"]:
                names = " | ".join(f"{n['text']!r}@{n['left']}" for n in h["names"])
                out.append(f"    head {h['text'][:34]!r:38} {names}")
            for s in b["slots"]:
                out.append(f"    BUDGET col{s['col']}: card {s['card']} = padding "
                           f"{s['padding']} + team {s['team']} + who {s['who']} + "
                           f"metrics {s['metrics']}   cells {s['cells']}")
            out.append("    🚨 DISTINCT LEFT EDGES PER METRIC COLUMN (1 = aligned):")
            for e in b["edges"]:
                flag = "✅" if e["distinct"] == 1 else "🚨"
                out.append(f"       {flag} col{e['col']} metric{e['idx']}: "
                           f"{e['distinct']} distinct of {e['n']} values, "
                           f"x-spread {e['spread']}px")
            if b["gaps"]:
                g = [x["gap"] for x in b["gaps"]]
                out.append(f"    WHITE SPACE name-end -> metrics-start: "
                           f"min {min(g)} max {max(g)} "
                           f"mean {sum(g) / len(g):.1f}  (n={len(g)})")
            out.append(f"    JERSEY beside {b['jersey']['beside']} · "
                       f"above {b['jersey']['above']} · none {b['jersey']['none']}")
            for s in b["spread"]:
                out.append(f"    PRIMARY col{s['col']}: max {s['max']} min {s['min']} "
                           f"min/max {s['ratio']}  distinct {s['distinct']} "
                           f"{s['values']}  (n={s['n']})")
            rk = b["teamRanked"]
            boxes = [(t["logoClass"], t["paintedW"], t["paintedH"], t["square"])
                     for t in b["teamRanked"]]
            out.append(f"    🚨 PAINTED LOGO BOX (ranked sample): {boxes[:2]}")
            sq = [t for t in b["teamRanked"] if t["square"]]
            out.append(f"       square on {len(sq)} of {len(b['teamRanked'])} ranked · "
                       f"{b['teamAllSquare']} of {b['teamAllCount']} ALL CARDS · "
                       f"monogram branch {b['monogramCount']}")
            ub = [(t["logoClass"], t["paintedW"], t["paintedH"], t["square"])
                  for t in b["teamUnranked"]]
            out.append(f"    🚨 PAINTED LOGO BOX (unranked sample): {ub}")
            out.append(f"    TEAM BLOCK: {len(rk)} ranked · "
                       f"rank on the logo's line {sum(1 for t in rk if t['rankWithLogo'])} · "
                       f"on the abbreviation's line "
                       f"{sum(1 for t in rk if t['rankWithAbbr'])} · "
                       f"underlined {sum(1 for t in rk if t['rankUnderlined'])}")
            if b["teamUnranked"]:
                out.append(f"      unranked sample (w,h): "
                           f"{[(t['width'], t['h']) for t in b['teamUnranked']]}")
    return "\n".join(out)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    data = run(scheme)
    print(summarise(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
