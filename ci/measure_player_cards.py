r"""The player cards' budget: every slot in pixels, and what wraps. Measured in a browser.

🚨 A212. Marc: *"At 3 columns wide, we have more than enough real estate in each of the player
cards… Overall - poor use of the real estate."* — so the first job is to say where the room
actually goes, slot by slot, the way `matchup.py` reports its row budget.

⚠️ MEASURING A BOX THAT IS ALREADY WRAPPING RETURNS THE BOX, NOT THE TEXT (A190's lesson). The
widest-case team line is measured by cloning the line into an off-screen `white-space:nowrap`
box, which is what `ci/measure_header_widths.py` does and why it exists.

🚨 AND THE LINE COUNT COMES FROM THE TEXT'S OWN HEIGHT, NOT FROM A RECT COUNT —
`Range.getClientRects()` returns a rect per FRAGMENT (A217's R-2623), and a Range over a cell
whose child is `display:block` measures the CHILD (A218's finding). `textContent`, never
`innerText` (R-2455).

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_player_cards.py            # light
    python ci/measure_player_cards.py dark
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                              # noqa: E402

WIDTHS = (1440, 1024)

MEASURE = r"""() => {
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;left:-9999px;';
  const host = document.querySelector('[data-testid="stAppViewContainer"]') || document.body;
  host.appendChild(probe);
  const unwrapped = (el) => {
    // clone the LINE into a nowrap box: what it wants, not what the box gave it
    const c = el.cloneNode(true);
    c.style.whiteSpace = 'nowrap';
    c.style.width = 'auto';
    c.style.maxWidth = 'none';
    probe.innerHTML = '';
    probe.appendChild(c);
    return c.getBoundingClientRect().width;
  };
  const linesOf = (el) => {
    const cs = getComputedStyle(el);
    const lh = parseFloat(cs.lineHeight) || 16;
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let top = Infinity, bottom = -Infinity, n;
    while ((n = w.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const rect of r.getClientRects()) {
        if (!rect.height) continue;
        top = Math.min(top, rect.top); bottom = Math.max(bottom, rect.bottom);
      }
    }
    return top === Infinity ? 1 : Math.max(1, Math.round((bottom - top) / lh));
  };

  const boards = [...document.querySelectorAll('.cfdb-cardboard')];
  const out = boards.map((board, bi) => {
    const cards = [...board.querySelectorAll('.cfdb-card')];
    const heads = [...board.querySelectorAll('.cfdb-cardcol-head')].map(h => ({
      text: (h.textContent || '').trim(),
      fontSize: getComputedStyle(h).fontSize,
      fontWeight: getComputedStyle(h).fontWeight,
      w: +h.getBoundingClientRect().width.toFixed(1)}));
    let teamWrapped = 0, worstTeam = '', worstTeamW = 0, ranked = 0;
    const slots = [];
    const units = new Set();
    cards.forEach(card => {
      const team = card.querySelector('.cfdb-card-team');
      const who = card.querySelector('.cfdb-card-who');
      const mets = card.querySelector('.cfdb-card-metrics, .cfdb-card-stat');
      if (team) {
        const hasRank = !!team.querySelector('.cfdb-rank');
        if (hasRank) ranked += 1;
        const identity = team.querySelector('.cfdb-identity') || team;
        // 🚨 LINE BANDS, NOT TEXT LINES. `.cfdb-card-team .cfdb-team` is `flex:0 0 100%`, so
        // the abbreviation ALWAYS takes its own line by design — a text-line count therefore
        // reads 2 for every ranked card whether or not anything is wrong, and the first run
        // of this script reported the wrap count unchanged after a fix that worked. The
        // defect is a THIRD band: logo / badge / name, where an unranked card has two.
        const kids = [...identity.querySelectorAll('.cfdb-logo-box, .cfdb-rank, .cfdb-team')]
            .filter(n => { const r = n.getBoundingClientRect();
                           return r.width > 0.5 && r.height > 0.5; });
        const bands = new Set(kids.map(n =>
            Math.round(n.getBoundingClientRect().top / 4) * 4)).size;
        if (bands > 2) {
          teamWrapped += 1;
          const want = unwrapped(identity);
          if (want > worstTeamW) {
            worstTeamW = want;
            worstTeam = (identity.textContent || '').trim().slice(0, 22);
          }
        }
      }
      if (slots.length < 1 && team && who && mets) {
        const px = (el) => +el.getBoundingClientRect().width.toFixed(1);
        const cs = getComputedStyle(card);
        slots.push({
          card: px(card),
          padding: +(parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)).toFixed(1),
          team: px(team), who: px(who), metrics: px(mets),
          metricGap: getComputedStyle(mets).gap,
          metricCount: mets.querySelectorAll('.cfdb-card-metric').length,
          metricWidths: [...mets.querySelectorAll('.cfdb-card-metric')].map(px),
        });
      }
      card.querySelectorAll('.cfdb-card-unit').forEach(u => {
        const t = (u.textContent || '').trim();
        if (t) units.add(t);
      });
    });
    return {board: bi, cards: cards.length, ranked, teamWrapped,
            worstTeam, worstTeamWanted: +worstTeamW.toFixed(1),
            heads, slot: slots[0] || null, units: [...units].sort()};
  });
  // the section headings the sub-headers must stay under
  const sections = [...document.querySelectorAll('h3')].map(h => ({
    text: (h.textContent || '').trim().slice(0, 28),
    fontSize: getComputedStyle(h).fontSize,
    fontWeight: getComputedStyle(h).fontWeight}));
  // the bold sub-section labels (Player yardage / Touchdowns / Defensive leaders)
  const labels = [...document.querySelectorAll('[data-testid="stMarkdownContainer"] strong')]
      .map(s => ({text: (s.textContent || '').trim().slice(0, 24),
                  fontSize: getComputedStyle(s).fontSize,
                  fontWeight: getComputedStyle(s).fontWeight}));
  probe.remove();
  return {boards: out, sections, labels};
}"""


def measure(scheme: str = "light", shot_prefix: str = "") -> list:
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
            for _ in range(5):
                page.mouse.wheel(0, 18000)
                page.wait_for_timeout(1300)
            page.wait_for_timeout(2000)
            data = page.evaluate(MEASURE)
            data.update(width=width, scheme=scheme,
                        dialogs=page.locator('[role="dialog"]').count())
            rows.append(data)
            if shot_prefix:
                out = Path("/Users/marcalexander/projects/ai_orchestrator_claude/"
                           "ncaa_football/claude_work/renders")
                out.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out / f"{shot_prefix}_{width}_{scheme}.png"))
            ctx.close()
        browser.close()
    return rows


def summarise(rows: list) -> str:
    out = []
    for d in rows:
        out.append(f"=== {d['width']} {d['scheme']} — {len(d['boards'])} card boards, "
                   f"dialogs {d['dialogs']} ===")
        for s in d["sections"][:4]:
            out.append(f"    section h3 {s['fontSize']:>7} w{s['fontWeight']:<4} {s['text']!r}")
        for lab in d["labels"][:6]:
            out.append(f"    label      {lab['fontSize']:>7} w{lab['fontWeight']:<4} "
                       f"{lab['text']!r}")
        for b in d["boards"]:
            out.append(f"  board {b['board']}: {b['cards']} cards, {b['ranked']} ranked, "
                       f"TEAM LINES WRAPPED: {b['teamWrapped']}"
                       + (f"  worst {b['worstTeam']!r} wants {b['worstTeamWanted']}px"
                          if b['teamWrapped'] else ""))
            for h in b["heads"]:
                out.append(f"      sub-header {h['fontSize']:>7} w{h['fontWeight']:<4} "
                           f"{h['w']:>6}px {h['text']!r}")
            if b["slot"]:
                s = b["slot"]
                out.append(f"      BUDGET card {s['card']}px = padding {s['padding']} + "
                           f"team {s['team']} + who {s['who']} + metrics {s['metrics']}"
                           f"  (gap {s['metricGap']}, {s['metricCount']} metrics "
                           f"{s['metricWidths']})")
            out.append(f"      units in cells: {b['units']}")
    return "\n".join(out)


if __name__ == "__main__":
    scheme = sys.argv[1] if len(sys.argv) > 1 else "light"
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    data = measure(scheme, prefix)
    print(summarise(data), file=sys.stderr)
    print(json.dumps(data, indent=1))
