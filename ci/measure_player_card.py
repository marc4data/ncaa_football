"""Is anything on a Today player card cut off? Measured in a real browser.

🚨 THIS EXISTS BECAUSE THREE SEPARATE WIDTHS ON THIS CARD WERE MEASURED WRONG IN ONE ROUND,
ALL THE SAME WAY. A192 read the widest team abbreviation as 28.3px (it is 41.6), the widest
metric cell as 19px (it is 25.4), and A191 read the `4th qtr` header as 58px (it is 82.9).

⚠️ THE COMMON CAUSE IS WORTH STATING ONCE: **a `Range.getBoundingClientRect()` over an
element that has already been clipped or wrapped returns its BOX, not its TEXT.** Every one
of those elements carries `overflow:hidden; text-overflow:ellipsis`, so the number that comes
back is the width it was given — the layout read back to itself, wearing the costume of a
measurement. Sizing a track from it guarantees the track is too small, and the too-small
track then confirms the reading.

✅ SO EVERY WIDTH HERE IS TAKEN FROM A CLONE IN AN OFF-SCREEN `white-space:nowrap; width:auto`
BOX, where the element is free to be its full size, and the check is always
**one-line need vs actual slot**.

⚠️ NOT PART OF THE TEST SUITE, DELIBERATELY — the call `ci/measure_chart_heights.py` and
`ci/measure_header_widths.py` both make. It needs Chromium, a serving tunnel and a running
Streamlit, so making it a test would mean a conditional skip, and a guard that skips itself
is the failure mode this project has spent a fortnight removing. `tests/test_today_cards.py`
holds the assertions that CAN be made deterministically and imports `CARD_WIDTHS_PX` from
here, so the constants have exactly one home.

    streamlit run site/app.py --server.port 8599 --server.headless true
    python ci/measure_player_card.py                       # all four widths
    python ci/measure_player_card.py --check               # exit 1 if anything is cut
"""
import sys

# 📊 MEASURED BY THIS FILE, 2026-09-21, against a live `today.body()` at 2026 week 3 — every
# one a CLONE measurement, so every one is the text's own width rather than its slot's.
#
# ⚠️ THESE ARE WHAT `site/lib/theme.py`'s `--cfdb-card-*` custom properties are derived from.
# If a re-measure moves one, the CSS moves with it — that is the whole point of them living
# in one place instead of being retyped into a stylesheet and a test.
CARD_WIDTHS_PX = {
    # the surname is the one thing that may never be truncated, at any supported width
    "widest_last_name": 109.2,      # "Chambers-Smith"
    "widest_first_name": 61.5,      # "Jaron-Keawe"
    "widest_abbreviation": 41.6,    # "MRMK"
    # ⚠️ NOT A VALUE — A UNIT LABEL. The touchdowns board passes `stat_label="touchdowns"`,
    # so its unit cell draws the whole word where the yardage board draws "YDS". The first
    # recording here said 25.4 (a three-digit value) because the probe had only ever looked
    # at the yardage board, which is the first one on the page. **The widest thing in a
    # metrics block is not in the column the eye goes to first.**
    "widest_metric_cell": 59.8,     # "touchdowns", on the touchdowns board
    "widest_metric_value": 25.4,    # a three-digit value, e.g. "483"
    "widest_jersey": 25.5,
    "card_logo": 28.0,
}

# The widths the site is expected to work at. 1100 is the floor A192 was given.
VIEWPORTS = (1100, 1280, 1440, 1680)

_PROBE = r"""() => {
  const host = document.createElement('div');
  host.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden';
  document.body.appendChild(host);

  // 🚨 THE ONLY HONEST MEASUREMENT ON THIS PAGE: clone it somewhere it cannot be clipped.
  const oneLine = el => {
    const c = el.cloneNode(true);
    c.style.whiteSpace = 'nowrap'; c.style.width = 'auto'; c.style.maxWidth = 'none';
    c.style.overflow = 'visible'; c.style.display = 'inline-block';
    host.innerHTML = ''; host.appendChild(c);
    return +c.getBoundingClientRect().width.toFixed(1);
  };
  const slot = el => +el.getBoundingClientRect().width.toFixed(1);

  const out = {cut: {last: [], abbr: [], metric: []}, widest: {}, cards: 0, heights: []};
  const widest = (k, v, t) => { if (!out.widest[k] || v > out.widest[k].px)
                                  out.widest[k] = {px: v, text: t}; };

  for (const card of document.querySelectorAll('.cfdb-card')) {
    out.cards++;
    out.heights.push(Math.round(card.getBoundingClientRect().height));

    const last = card.querySelector('.cfdb-player-last');
    if (last) {
      const n = oneLine(last), s = slot(last), t = last.innerText.trim();
      widest('last_name', n, t);
      if (n > s + 0.5) out.cut.last.push({text: t, need: n, slot: s});
    }
    const abbr = card.querySelector('.cfdb-card-team .cfdb-team');
    if (abbr) {
      const n = oneLine(abbr), s = slot(abbr), t = abbr.innerText.trim();
      widest('abbreviation', n, t);
      if (n > s + 0.5) out.cut.abbr.push({text: t, need: n, slot: s});
    }
    for (const el of card.querySelectorAll('.cfdb-card-value, .cfdb-card-unit')) {
      const n = oneLine(el), s = slot(el), t = el.innerText.trim();
      widest('metric_cell', n, t);
      if (n > s + 0.5) out.cut.metric.push({text: t, need: n, slot: s});
    }
  }
  host.remove();
  return out;
}"""


def measure(url: str, viewports=VIEWPORTS) -> dict:
    """{viewport: probe result}, with every card mounted before it is read."""
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for width in viewports:
            page = browser.new_page(viewport={"width": width, "height": 1400},
                                    color_scheme="light")
            page.goto(url, wait_until="networkidle", timeout=90_000)
            page.wait_for_selector(".cfdb-cardboard", timeout=90_000)
            page.wait_for_timeout(3000)
            # ⚠️ STREAMLIT MOUNTS THE LOWER BOARDS AS THE PAGE IS SCROLLED. A probe that reads
            # from the top reports only what happens to be mounted — A192's first run said
            # "0 truncated of 30" about a board of 150, which is a third of an answer.
            for _ in range(12):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(300)
            page.wait_for_timeout(1500)
            results[width] = page.evaluate(_PROBE)
            page.close()
        browser.close()
    return results


def main(argv) -> int:
    check = "--check" in argv
    url = next((a for a in argv if a.startswith("http")),
               "http://127.0.0.1:8599/today"
               "?season=2026&season_type=regular&week=3&tab=back")
    results = measure(url)

    failed = False
    for width, r in results.items():
        cut = r["cut"]
        total = len(cut["last"]) + len(cut["abbr"]) + len(cut["metric"])
        heights = r["heights"] or [0]
        mark = "OK " if total == 0 else "CUT"
        if total:
            failed = True
        print(f"{mark} {width}px  {r['cards']} cards  "
              f"height {min(heights)}-{max(heights)}px  "
              f"cut: surname {len(cut['last'])}, abbreviation {len(cut['abbr'])}, "
              f"metric {len(cut['metric'])}")
        for kind in ("last", "abbr", "metric"):
            for item in cut[kind][:3]:
                print(f"      {kind}: {item['text']!r} needs {item['need']} "
                      f"in {item['slot']}")

    print("\nwidest drawn, across every viewport:")
    for key in ("last_name", "abbreviation", "metric_cell"):
        best = max((r["widest"].get(key) or {"px": 0, "text": "-"}
                    for r in results.values()), key=lambda x: x["px"])
        recorded = CARD_WIDTHS_PX.get(f"widest_{key}")
        stale = recorded is not None and recorded + 0.5 < best["px"]
        if stale:
            failed = True
        print(f"   {key:<14} {best['px']:>7}px  {best['text']!r:<18}"
              f"recorded {recorded}{'   <- RECORDED VALUE IS STALE' if stale else ''}")

    return 1 if check and failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
