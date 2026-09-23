r"""A213 — a ranked card occupies the same line bands as an unranked one (cfdb-main-R-2545).

> **MARC, v14:** *"Cards with Ranked teams are word-wrapping an extra line."*

📊 MEASURED ON THE REAL PAGE, the five contributors to the team line's first band, on `#3ND`
in a 44px track (`ci/measure_player_cards.py`, 1440 and 1024, light and dark):

    contributor                                      before    after
    logo box (inline style from logo_or_monogram)     28.00    18.00
    `.cfdb-logo-box` margin-right  (theme.py:1553)     6.40     0.00
    the flex container's column-gap (theme.py:1240)    3.20     3.20
    `.cfdb-rank` margin-left       (theme.py:1043)     4.80     0.00
    the badge itself                                  12.17    12.17
                                        FIRST BAND    54.57    33.37   of 44px
                        worst case, a `#20` badge     60.65    39.45   of 44px

    BANDS   before  12 of 12 ranked cards at 3, 138 unranked at 2
            after   12 of 12 ranked cards at 2, 138 unranked at 2

🚨 THE ROOT CAUSE IS AN INLINE STYLE, NOT A SPECIFICITY LOSS. `identity.logo_or_monogram`
writes `style='width:28px'` onto the element, and an inline style beats every selector short
of `!important` — so `theme.py`'s `.cfdb-card-team .cfdb-logo-box { width:18px }` was never in
the contest. **A212 read that rule, saw 28px, and recorded it as a rule "not winning".**

⚠️ THESE TESTS ANCHOR ON THE EMITTED MARKUP, NOT ON A WORD IN A FILE (A217's R-2624). The
question is *what does the producer write*, and only rendering it can answer that — asserting
that `18` appears in `today.py` would pass on this docstring.

⚠️ AND THE BAND COUNT ITSELF CANNOT RUN HERE: it needs a browser and live published serving,
neither of which CI has. `ci/measure_player_cards.py` is that instrument and the report carries
its numbers. **What CI can hold is the producer contract the band count depends on**, which is
the three facts below.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import table                                         # noqa: E402
from views import today                                       # noqa: E402

ROW = pd.Series({
    "player_slug": "micah-gilbert", "player_name": "Micah Gilbert", "jersey": 14,
    "team_slug": "notre-dame", "team_display": "Notre Dame", "team_abbreviation": "ND",
    "team_logo_url": "https://example.invalid/nd.png", "team_rank": 3,
    "team_color": "#0C2340", "stat_value": 170.0,
})


def _logo_widths(markup: str) -> list:
    """Every `width:NNpx` the logo/monogram span declares, in order."""
    import re
    return [int(m) for m in re.findall(r"width:(\d+)px", markup)]


# ── the producer carries the size, because no stylesheet can ──────────────────────────

def test_the_card_asks_for_an_eighteen_pixel_logo():
    """🚨 THE WHOLE FIX IS HERE. A 28px disc in a 44px track leaves 16px for a rank badge
    that needs 12.17 plus 11.2 of margins and gap, so the badge wraps to a third band."""
    markup = today._player_card(ROW, "touchdowns")
    widths = _logo_widths(markup)
    assert widths, "the card rendered no sized logo box at all"
    assert set(widths) == {today._CARD_LOGO_PX}, (
        f"the card's logo draws {sorted(set(widths))}px, not {today._CARD_LOGO_PX}px — "
        "the size is written as an INLINE STYLE by `identity.logo_or_monogram`, so a CSS "
        "rule cannot correct this; the call path has to pass it")
    assert today._CARD_LOGO_PX <= 18, (
        f"at {today._CARD_LOGO_PX}px the first band needs "
        f"{today._CARD_LOGO_PX + 3.2 + 18.25:.2f}px of the 44px team track")


def test_every_other_caller_still_gets_the_twenty_eight_pixel_row_logo():
    """⚠️ `table.team_cell` IS SHARED — Schedule, Scores, Standings and the Team page all read
    it, and a 28px disc is the table-row affordance. §3 rule 3.1: the parameter ships with the
    default, and a call site that wants something else passes it."""
    markup = table.team_cell(ROW, "team_slug", "team_display", "team_logo_url", "team_rank")
    assert set(_logo_widths(markup)) == {28}, (
        "changing `team_cell`'s default resizes every team logo in every table on the site")


def test_a_team_with_no_logo_keeps_the_card_footprint(monkeypatch):
    """🚨 AC-G.28 — THE MONOGRAM BRANCH IS A DIFFERENT CLASS AND MUST DRAW THE SAME BOX.
    `.cfdb-monogram-empty` carries its own `margin-right:.4rem` (theme.py:951), so a card-scoped
    reset naming only `.cfdb-logo-box` would give the two branches different footprints — the
    exact promise AC-G.28 makes. 📊 Zero cards took this branch on the week measured, which is
    why only a test can hold it."""
    blank = ROW.copy()
    blank["team_logo_url"] = None
    with_logo = _logo_widths(today._player_card(ROW, "touchdowns"))
    without = _logo_widths(today._player_card(blank, "touchdowns"))
    assert without, "the monogram branch rendered no sized box"
    assert set(without) == set(with_logo), (
        f"logo branch draws {sorted(set(with_logo))}px and the monogram branch "
        f"{sorted(set(without))}px — a missing logo would shift the card (AC-G.28)")


def test_the_card_resets_both_margins_that_push_the_badge_off_the_line():
    """📊 18px ALONE IS NOT ENOUGH AND THE ARITHMETIC SAYS SO: 18 + 6.4 + 3.2 + 4.8 + 12.17 =
    44.57 against a 44px track, and a two-digit badge needs 50.65. **Both margins are written
    for the inline table-row context**, where there is no flex gap; inside the card
    `.cfdb-identity`'s own `column-gap` already does that job and they double-count.

    ⚠️ ANCHORED ON THE DECLARATION, NOT ON THE WORD (R-2624) — the selector must reset the
    property, and naming both classes is AC-G.28's half of it.
    """
    import re
    # 🚨 COMMENTS COME OUT FIRST, AND THE FIRST DRAFT OF THIS TEST PROVED WHY. `theme.py`
    # documents every rule it carries, so the prose ABOUT a selector outnumbers the rule using
    # it — and the comment three lines above this very reset quotes the old selector verbatim.
    # The draft matched that comment, found `width:18px` inside the block after it, and failed
    # on a rule that was present and correct. **R-2624's family: anchor on a declaration, and
    # make sure the text you are searching contains only declarations.**
    theme = re.sub(r"/\*.*?\*/", "", (ROOT / "site" / "lib" / "theme.py").read_text(),
                   flags=re.S)
    # every (selector list, declaration block) pair, comments already gone
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", theme)
    for selector, prop in (
            (".cfdb-card-team .cfdb-logo-box", "margin-right"),
            (".cfdb-card-team .cfdb-monogram-empty", "margin-right"),
            (".cfdb-card-team .cfdb-rank", "margin-left")):
        # ⚠️ THE SELECTOR MAY BE ANY MEMBER OF A COMMA LIST, not the one that starts the line —
        # naming `.cfdb-logo-box` and `.cfdb-monogram-empty` in ONE rule is the point of the
        # fix, so a line-start anchor would refuse the correct shape.
        blocks = [b for sels, b in rules
                  if any(part.strip() == selector for part in sels.split(","))]
        assert blocks, f"no rule declares {selector}"
        found = [m.group(1).strip() for b in blocks
                 for m in [re.search(rf"(?:^|;)\s*{prop}\s*:\s*([^;}}]+)", b)] if m]
        assert found, f"{selector} does not reset {prop}"
        assert found[-1] in ("0", "0px", "0rem"), (
            f"{selector} sets {prop}:{found[-1]} — it must be 0 inside a card, "
            "or the badge is pushed onto a third line")
