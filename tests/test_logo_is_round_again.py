r"""A223 — the logo is a disc again, the tab names its game, and 8–14 reads apart from 15+.

## PART 0 — the regression A221 shipped and its own report did not see

📊 MEASURED ON ALL 150 CARDS, at 1440 and 1024, both themes (`ci/measure_card_budget.py`):

    before   painted logo box 41.66..57.59 wide x 18 tall   — SQUARE ON 0 OF 150
    after    18 x 18                                        — square on 90 of 90, x2 themes

🚨 **A221 PUT `flex:0 0 100%` ON `.cfdb-logo-box`, WHICH IS THE PAINTED ELEMENT.** It carries
`border-radius:50%` and a gray background from its base rule while the `<img>` keeps its own
18px inline size, **so the disc stretched into a pill with the mark at its left edge.** The
layout A221 wanted was right and is kept; only how it is achieved has moved.

⚠️ **AND A221's TEST ASSERTED THE DEFECT.** It required `flex:0 0 100%` on the logo box, so it
was green on every one of those 150 pills. **The acceptance is the painted box, not the block**
— A221's report measured the team BLOCK at 57.59 × 33.19 and called it correct, which it was.

## PART 1 — `tab.teams_suffix` existed, was tested, and nobody called it

📊 `git grep teams_suffix` at `bdc41ba`: one definition, four comments, eight assertions —
**zero call sites.** `app.py`'s own comment said a page refines its title *"see views/today.py,
and Matchup's team abbreviations"*; Today does, Matchup never did. §2.5's class.

## PART 2 — the ladder, measured against the real page

    light  page #ffffff   u1 #d9a406   u2 #5f5f67 -> #87878d   u3 #16191d
    dark   page #0e1117   u1 #e8b931   u2 #7b7b83 -> #606068   u3 #f2f5f8

    steps  light  u1|u2 2.79 -> 1.58   u2|u3 2.79 -> 4.94
           dark   u1|u2 2.28 -> 3.39   u2|u3 3.84 -> 5.69
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import tab                                             # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
APP = (ROOT / "site" / "app.py").read_text()
TABSRC = (ROOT / "site" / "lib" / "tab.py").read_text()


def rule(selector: str) -> str:
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


def _rgb(hexstr: str):
    h = hexstr.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = [f(x) for x in c]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(_rgb(a)), _lum(_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def token(name: str):
    """The two resolved sides of a `light-dark()` token."""
    m = re.search(rf"--{name}:\s*light-dark\((#[0-9a-fA-F]{{6}}),\s*(#[0-9a-fA-F]{{6}})\)",
                  THEME)
    assert m, f"--{name} is not a light-dark() pair any more"
    return m.group(1), m.group(2)


# ── PART 0: the painted box is square ────────────────────────────────────────────────

def test_the_painted_logo_box_never_claims_the_line():
    """🚨 THE ASSERTION A221 SHOULD HAVE MADE. `.cfdb-logo-box` paints the disc — a background
    and a 50% radius — so anything that changes its main size changes the disc."""
    logo = rule(".cfdb-card-team .cfdb-logo-box,")
    assert not re.search(r"flex\s*:\s*0 0 100%", logo), logo
    assert not re.search(r"[;{]\s*width\s*:", logo), (
        f"a width on the painted box is the same defect by another route: {logo}")


def test_a_zero_height_pseudo_element_claims_the_line_instead():
    breaker = rule(".cfdb-card-team .cfdb-identity::before,")
    assert re.search(r"flex\s*:\s*0 0 100%", breaker), breaker
    assert "height:0" in breaker.replace(" ", ""), (
        "a line breaker with height is a painted element again")
    assert "content:''" in breaker.replace(" ", "") or 'content:""' in breaker.replace(" ", "")


def test_both_containers_carry_the_break():
    """⚠️ BOTH SHAPES OCCUR (A191). `_team_identity` wraps in an anchor only when the row has a
    slug, so a team without one renders the logo directly inside `.cfdb-identity`. A rule
    naming one of the two fixes most cards and silently leaves the rest."""
    for selector in (".cfdb-card-team .cfdb-identity::before",
                     ".cfdb-card-team .cfdb-teamlink::before"):
        assert selector in THEME, f"{selector} is missing; one of the two shapes is unfixed"


def test_the_order_is_set_on_every_item_not_only_the_break():
    """🚨 AN ITEM WITH NO `order` DEFAULTS TO 0 AND SORTS BEFORE THE PSEUDO-ELEMENT, whatever
    the source order says. The break is only a break if everything around it is ordered."""
    for selector, expected in ((".cfdb-card-team .cfdb-logo-box,", "order:1"),
                               (".cfdb-card-team .cfdb-rank {", "order:3"),
                               (".cfdb-card-team .cfdb-team {", "order:4")):
        block = rule(selector)
        assert expected in block.replace(" ", ""), (selector, block)
    assert "order:2" in rule(".cfdb-card-team .cfdb-identity::before,").replace(" ", "")


def test_the_monogram_branch_is_ordered_with_the_logo_branch():
    """🚨 AC-G.28 — THE TWO BRANCHES MUST HAVE THE SAME FOOTPRINT, and `.cfdb-monogram-empty`
    is a different class from `.cfdb-logo-box`. 📊 **Zero cards take the monogram branch on the
    current boards**, so nothing on the live page would show this — only a test can hold it."""
    # 🚨 AIMED AT THE `order` RULE SPECIFICALLY, AND THE FIRST DRAFT WAS NOT. It looked up
    # `.cfdb-card-team .cfdb-logo-box,` — and A213's margin reset starts with the SAME selector
    # list and also names the monogram, so under a staged break that stripped the monogram from
    # the ORDER rule this test matched the margin rule instead and stayed GREEN. **A helper that
    # finds a different rule with the same prefix is R-758's third mode, in the lookup.**
    ordered = [block for block in re.findall(r"^([^\n{}]*\{[^}]*\})", THEME, re.M)
               if "order:1" in block.replace(" ", "")]
    assert ordered, "nothing carries order:1 any more; the break is unordered"
    assert any(".cfdb-monogram-empty" in block for block in ordered), (
        f"the monogram branch is not ordered with the logo branch (AC-G.28): {ordered}")


# ── PART 1: the tab names its game ───────────────────────────────────────────────────

def test_a_non_matchup_route_does_no_work_at_all(monkeypatch):
    """⚠️ THE OTHER SEVENTEEN PAGES MUST NOT CHANGE — and asserting `is None` DOES NOT PROVE IT.

    🚨 THE FIRST VERSION OF THIS TEST CAME BACK GREEN UNDER ITS OWN STAGED BREAK. With the
    route check deleted, `route_suffix("today")` still returned None — because the query fails
    outside a Streamlit runtime and the guard swallows it. **The test could not tell
    "route-keyed" from "the database is unreachable in tests".** R-760's class: an assertion
    nothing the code can produce would falsify.

    ✅ SO IT ASSERTS THE ROUTE IS CHECKED *FIRST*: on a non-matchup route the URL is never read.
    """
    import lib.params as params
    seen = []
    monkeypatch.setattr(params, "get", lambda *a, **k: seen.append(a) or None)
    for route in ("today", "schedule", "odds", None, ""):
        assert tab.route_suffix(route) is None, route
    assert seen == [], (
        f"a non-matchup route read the URL {len(seen)} time(s) — the route is not the gate")


def test_the_suffix_can_never_kill_the_shell(monkeypatch):
    """🚨 IT RUNS OUTSIDE ANY PAGE BODY, so `states.section` never sees an exception: an
    unguarded failure here does not draw an Error card, **it kills the site** and prints a
    traceback with absolute paths on screen (AC-G.9). A130 rendered that failure rather than
    reasoning about it — `claude_work/renders/A130_unguarded_title_failure.png`."""
    import lib.params as params

    def boom(*a, **k):
        raise RuntimeError("the database is gone")
    monkeypatch.setattr(params, "get", boom)
    assert tab.route_suffix("matchup") is None


def test_app_asks_the_route_for_its_suffix():
    """🚨 THE CALL IS IN THE SHELL, NOT IN `matchup.py`, WHICH IS SESSION B's (§3.2.2)."""
    assert re.search(r"tab\.route_suffix\(", APP), (
        "app.py no longer asks the route for a suffix; Matchup's tab is generic again")
    assert "route_suffix" in TABSRC
    matchup = ROOT / "site" / "views" / "matchup.py"
    assert "route_suffix" not in matchup.read_text(), (
        "session B's file must not be edited for a browser title")


def test_the_suffix_is_built_from_published_abbreviations():
    """⚠️ §4.2.1 IS NOT ENGAGED — joining two published strings creates no quantity, which is
    `teams_suffix`'s own note. And the query is one single-table SELECT on a relation the page
    already reads."""
    body = TABSRC[TABSRC.index("def route_suffix"):]
    assert "from srv_game" in body
    assert "join" not in body.lower().split("except")[0].replace("joining", "")
    assert "away_abbreviation" in body and "home_abbreviation" in body


def test_teams_suffix_still_behaves(monkeypatch):
    """⚠️ A130's EIGHT ASSERTIONS STILL HOLD — this round wires the function up, it does not
    change it. One check here so a future edit to `teams_suffix` cannot pass unnoticed."""
    import pandas as pd
    row = pd.Series({"away_abbreviation": "USM", "home_abbreviation": "AUB"})
    assert tab.teams_suffix(row) == "USM @ AUB"


# ── PART 2: the ladder ───────────────────────────────────────────────────────────────

LIGHT_PAGE, DARK_PAGE = "#ffffff", "#0e1117"


def test_the_eight_to_fourteen_band_reads_apart_from_fifteen_plus():
    """> **MARC, v16:** *"Upset by 8-14 is too dark, not very discernable from Upset by 15+."*

    📊 `u2|u3` was **2.79:1** in light and 3.84:1 in dark. Those two are the only pair separated
    by luminance ALONE — both are neutral grays — so that is where the luminance has to go.
    """
    u2_light, u2_dark = token("cfdb-u2")
    u3_light, u3_dark = token("cfdb-u3")
    assert contrast(u2_light, u3_light) >= 4.0, (
        f"8-14 vs 15+ is {contrast(u2_light, u3_light)}:1 in light — Marc's complaint")
    assert contrast(u2_dark, u3_dark) >= 4.0, (
        f"8-14 vs 15+ is {contrast(u2_dark, u3_dark)}:1 in dark")


def test_the_band_still_clears_the_non_text_contrast_floor():
    """🚨 THIS IS WHY 50% WAS REJECTED, AND IT IS A MEASUREMENT RATHER THAN A PREFERENCE.
    50% puts the glyph at **2.19:1** on white and **2.01:1** on the dark page — under WCAG
    1.4.11's 3:1 for a non-text graphical object, which is what a filled circle is.
    ⚠️ A211 applied the 4.5:1 TEXT floor to this glyph; 3:1 is the applicable one for a shape,
    and naming which floor is being used is the whole reason the number can be defended."""
    u2_light, u2_dark = token("cfdb-u2")
    assert contrast(u2_light, LIGHT_PAGE) >= 3.0, contrast(u2_light, LIGHT_PAGE)
    assert contrast(u2_dark, DARK_PAGE) >= 3.0, contrast(u2_dark, DARK_PAGE)


def test_the_dark_theme_is_not_the_mirror_of_the_light_one():
    """🚨 R-547's LESSON. "Less ink" moves TOWARD the page in both themes — which lightens on
    white and **darkens** on #0e1117. A dark value that merely mirrored the light one would
    move toward the near-white `u3` and make Marc's pair worse."""
    u2_light, u2_dark = token("cfdb-u2")
    assert _lum(_rgb(u2_light)) > _lum(_rgb(u2_dark)), (
        "the dark band must be darker than the light one, not its mirror")


def test_the_other_two_bands_are_unchanged():
    """⚠️ MARC NAMED ONE RUNG. `u1` is 2.27:1 against a white page — under any floor — and that
    is **pre-existing, reported by A211, and still not this round's to fix.**"""
    assert token("cfdb-u1") == ("#d9a406", "#e8b931")
    assert token("cfdb-u3") == ("#16191d", "#f2f5f8")


def test_the_legend_reads_the_same_tokens_and_names_ranges_not_shades():
    """⚠️ §3.2.3 — IF THE LEGEND NAMED THE SHADES IT WOULD NOW BE WRONG. It does not: it reads
    `cfdb-u1/u2/u3` for its swatches and labels them with the RANGES from `metrics.upset_bands`,
    so the swatch and the glyph cannot disagree and no wording had to move."""
    glyphs = (ROOT / "site" / "lib" / "glyphs.py").read_text()
    for cls in ("cfdb-u1", "cfdb-u2", "cfdb-u3"):
        assert cls in glyphs, f"the legend no longer reads {cls}"
    titles = glyphs[glyphs.index("UPSET_LEVEL_TITLE"):glyphs.index("UPSET_AGAINST")]
    for shade in ("gray", "grey", "black", "dark", "light"):
        assert shade not in titles.lower(), (
            f"the legend names a shade ({shade!r}); it must name the range instead")
