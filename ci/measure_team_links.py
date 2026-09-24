r"""Team anchors on the player boards: how many, and WHERE THEY GO.

🚨 R-287 IS THE WHOLE REASON THIS MEASURES DESTINATIONS. Measured on the running page once:
**996 team anchors, 1 distinct href, 0 carrying a `team` parameter.** Every one pointed at
`/team` with no team — and *an anchor exists* passes on 996 links to nowhere.

⚠️ `params.link` DROPS a parameter set to `None` and returns a syntactically perfect
`/team?season=2026`, so a missing slug yields an anchor that looks right in a count and is
wrong in a click. **The distinct-href count and the non-empty `team=` are the only parts of
this that can fail for the reason that matters.**

🚨 AND THE "ALL" STATE IS REACHED THROUGH THE SIDEBAR, NEVER `?week=All` — that raises
BadParam and takes the page to zero panels (A225's R-3054, widened by A226's R-3057).

    streamlit run site/app.py --server.port 8604 --server.headless true
    python ci/measure_team_links.py
"""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.page_url import page_url                                  # noqa: E402

BOARDS = ("Player yardage", "Touchdowns", "Defensive leaders")

JS = """() => [...document.querySelectorAll('.cfdb-cardboard')].map((b) => ({
  cards: b.querySelectorAll('.cfdb-card').length,
  hrefs: [...b.querySelectorAll('.cfdb-teamlink')].map((a) => a.getAttribute('href')),
}))"""


def _pick_all(pg):
    box = pg.locator('[data-testid="stSelectbox"]').filter(has_text="Week").first
    box.click()
    pg.wait_for_timeout(900)
    pg.get_by_role("option", name="All", exact=True).click()


def run():
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for state, to_all in (("week 3", False), ("week All", True)):
            ctx = br.new_context(viewport={"width": 1440, "height": 1200})
            pg = ctx.new_page()
            pg.goto(f"http://localhost:8604{page_url('today')}?tab=back&week=3",
                    wait_until="networkidle", timeout=120000)
            pg.wait_for_timeout(8000)
            if to_all:
                _pick_all(pg)
            pg.wait_for_timeout(9000)
            for _ in range(8):
                pg.mouse.wheel(0, 18000)
                pg.wait_for_timeout(900)
            pg.wait_for_timeout(2500)
            assert pg.locator('[role="dialog"]').count() == 0, "a dialog is over the page"
            out[state] = pg.evaluate(JS)
            ctx.close()
        br.close()
    return out


def summarise(out) -> tuple:
    lines, ok = [], True
    for state, boards in out.items():
        lines.append(f"\n=== {state} ===")
        for i, b in enumerate(boards):
            name = BOARDS[i] if i < len(BOARDS) else str(i)
            hrefs = b["hrefs"]
            distinct = sorted(set(hrefs))
            teams = [parse_qs(urlparse(h).query).get("team", [""])[0] for h in hrefs]
            named = [t for t in teams if t]
            good = len(distinct) > 1 and len(named) == len(hrefs) and len(hrefs) > 0
            ok = ok and good
            lines.append(f"  {name:20} cards={b['cards']:>3} anchors={len(hrefs):>3} "
                         f"distinct hrefs={len(distinct):>3} "
                         f"carrying a non-empty team={len(named):>3}  "
                         f"{'✅' if good else '🚨'}")
            if hrefs:
                lines.append(f"      e.g. {distinct[0]}")
    return "\n".join(lines), ok


if __name__ == "__main__":
    data = run()
    text, ok = summarise(data)
    print(text)
    print(f"\nEVERY BOARD: >1 distinct href AND every anchor names a team: {ok}")
    sys.exit(0 if ok else 1)
