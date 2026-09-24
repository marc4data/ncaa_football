"""A192 — the player card's widths, held against the browser measurements they came from.

🚨 WHY THE NUMBERS ARE IMPORTED RATHER THAN WRITTEN HERE. A191 shipped six header widths that
existed twice — once in the page, once hand-copied into a test — and the copies disagreed
while the test stayed green, because a constant that lives only in a test is a second source
nothing can contradict. `ci/measure_player_card.py` owns these, re-derives them in a real
browser (`--check`), and this file asserts the CSS covers them.

⚠️ AND THIS FILE MEASURES NOTHING, DELIBERATELY. CI has no Chromium, no warehouse and no
Streamlit, so a browser assertion here would be a conditional skip — the R-575 failure mode.
What it CAN check is that the shipped CSS is consistent with the recorded measurements, and
that the specific mistakes A192 made cannot come back.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "ci"))

from measure_player_card import CARD_WIDTHS_PX            # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
IDENTITY = (ROOT / "site" / "lib" / "identity.py").read_text()
TODAY = (ROOT / "site" / "views" / "today.py").read_text()
MATCHUP = (ROOT / "site" / "views" / "matchup.py").read_text()


def _custom_property_px(name: str) -> float:
    """The declared value of a `--cfdb-*` custom property, in px. 1rem = 16px."""
    match = re.search(rf"{re.escape(name)}:\s*([0-9.]+)(rem|px)\s*;", THEME)
    assert match, f"{name} is not declared in theme.py"
    value = float(match.group(1))
    return value * 16 if match.group(2) == "rem" else value


def test_the_name_floor_covers_the_widest_surname_that_actually_renders():
    """🚨 THE RULE A192 EXISTS FOR: the surname is never truncated, at any supported width.

    📊 Measured in Chromium against live serving at 2026 week 3: the widest surname drawn is
    "Chambers-Smith" at 109.2px. Before A192 the name got whatever the card had left after two
    oversized fixed tracks — **0px at 1100, 29.6px at 1280** — so it was truncated on 150 of
    150 cards at 1280 and on 67 of 150 at 1440.
    """
    floor = _custom_property_px("--cfdb-card-name-min")
    widest = CARD_WIDTHS_PX["widest_last_name"]
    assert floor >= widest, (
        f"--cfdb-card-name-min is {floor}px but the widest surname draws {widest}px — "
        f"re-measure with ci/measure_player_card.py; do not lower this floor")


def test_the_team_track_fits_the_widest_abbreviation():
    """🚨 A192 CUT THIS TRACK TO 30px AND CLIPPED 78 OF 150 ABBREVIATIONS.

    The 28.3px it sized from was a `Range` over an element that was already ellipsised, which
    returns its box and not its text. Measured from a clone in a nowrap box, "MRMK" is 41.6px.
    """
    track = _custom_property_px("--cfdb-card-team-w")
    widest = CARD_WIDTHS_PX["widest_abbreviation"]
    assert track >= widest, (
        f"--cfdb-card-team-w is {track}px but the widest abbreviation draws {widest}px")
    assert track >= CARD_WIDTHS_PX["card_logo"], (
        "the track must also hold the logo that sits above the name")


def test_the_surname_opts_out_of_the_ellipsis_on_todays_card_only():
    """The floor is worthless if the surname is still clipped inside it."""
    assert re.search(r"\.cfdb-card \.cfdb-player-last\s*{[^}]*overflow:\s*visible", THEME), (
        "the surname must escape the ellipsis inside a Today card, or the floor buys nothing")
    # ⚠️ AND ONLY THERE. Matchup shares `player_row` and must keep its ellipsis.
    assert not re.search(r"^\.cfdb-player-last\s*{[^}]*overflow:\s*visible", THEME, re.M), (
        "the opt-out must stay scoped to .cfdb-card; unscoped it would change Matchup")


def test_todays_overrides_beat_the_inline_style_they_have_to_beat():
    """🚨 AN INLINE `style=` OUTRANKS EVERY CLASS SELECTOR, AND THAT MADE TWO A192 RULES INERT.

    `identity.player_row` writes `min-width:0;white-space:nowrap;overflow:hidden;
    text-overflow:ellipsis` into the attribute of all three name elements. A192's
    `min-width:7rem` and `overflow:visible` were both written, both correct, and both lost to
    it — one surname was still being cut with the rule sitting in the sheet.

    ⚠️ THE TIDIER FIX WAS TRIED AND DELIBERATELY REVERTED. Moving those four declarations out
    of the attribute into a class rule is better CSS, and it broke three tests in
    `tests/test_matchup_postgame.py` and `tests/test_matchup_yardage.py`, which locate this
    markup by those literal strings — **session B's files.** A shared-module change that
    forces edits into the other session's tests is R-729's shape. `!important` in Today's own
    sheet is the canonical tool for beating an inline style and costs nobody else anything.

    🚨 SO THIS TEST PINS THE COUPLING IN BOTH DIRECTIONS: the inline clip must still be there
    (Matchup's tests read it) AND the overrides must still be marked (or they do nothing).
    """
    assert "min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" in IDENTITY, (
        "the inline clip is gone; session B's matchup tests match on these literals")

    for selector, declaration in (
            (r"\.cfdb-card \.cfdb-player-last", "overflow:visible !important"),
            (r"\.cfdb-card \.cfdb-player-name", "min-width:var(--cfdb-card-name-min) !important")):
        rule = re.search(rf"{selector}\s*{{([^}}]*)}}", THEME)
        assert rule, f"{selector} has no rule in theme.py"
        assert declaration in rule.group(1).replace("  ", " "), (
            f"{selector} must carry `{declaration}` — without the marker it loses to the "
            f"inline style and the rule silently does nothing")


def test_the_shared_row_puts_its_class_attribute_after_its_style():
    """⚠️ ATTRIBUTE ORDER IS LOAD-BEARING HERE, WHICH IS WHY IT IS ASSERTED.

    Session B's tests split on literals like `<div style='display:flex`. Emitting
    `class=` first breaks every one of them and forces edits into B's files; appending it
    leaves the prefixes byte-identical. CSS does not care about the order, so nothing is lost.
    """
    for literal in ("<div style='display:flex;align-items:stretch;gap:.4rem' "
                    "class='cfdb-player-row'>",
                    "class='cfdb-player-last'"):
        assert literal in IDENTITY.replace('f"', '').replace('"', ''), literal
    assert "<div class='cfdb-player-row'" not in IDENTITY, (
        "the class moved back in front of the style; B's string surgery breaks on that")


def test_the_metrics_are_content_sized_rather_than_equal_thirds():
    """🚨 `flex:1 1 0` SPLIT THE BLOCK INTO EQUAL THIRDS AND WRAPPED `483` UNDER ITS OWN UNIT.

    30 of 180 metric cells were drawing on two lines inside a 72px block, because the widest
    single cell governs all three when they are equal — and the widest is not a value but the
    touchdowns board's unit label, "touchdowns" at 59.8px.
    """
    assert re.search(r"\.cfdb-card \.cfdb-card-metric\s*{[^}]*flex:\s*0 0 auto", THEME)
    assert re.search(r"\.cfdb-card > \.cfdb-card-metrics\s*{[^}]*flex:\s*0 0 auto", THEME), (
        "the block must size to its content; a fixed track has to be guessed and was, twice")
    assert CARD_WIDTHS_PX["widest_metric_cell"] >= CARD_WIDTHS_PX["widest_metric_value"], (
        "the recorded widest cell must be the widest of values AND unit labels")


def test_class_and_position_leave_the_card_but_not_the_page():
    """Moved to the cell's `title`, not deleted — 24.2px the surname needed more."""
    assert re.search(r"\.cfdb-card \.cfdb-player-meta\s*{[^}]*display:\s*none", THEME)
    assert "who_title" in TODAY and "title=" in TODAY, (
        "hiding the pair without putting it in a title would simply lose it (AC-G.11)")
    assert "html.escape(who_title)" in TODAY, (
        "a position or class could carry an apostrophe; A191 shipped that bug once already")


def test_matchup_cannot_be_reached_by_todays_card_rules():
    """🚨 THE ISOLATION THE WHOLE APPROACH RESTS ON, ASSERTED RATHER THAN ASSUMED.

    Every Today rule A192 adds is scoped under `.cfdb-card`. That is only safe while Matchup
    — which calls the same `identity.player_row` — uses no such class. Verified in a browser
    too: 24 player rows on Matchup, none inside a `.cfdb-card`, `flex-wrap: nowrap`,
    `min-width: 0`, ellipsis intact, class and position still visible.
    """
    assert "cfdb-card" not in MATCHUP, (
        "matchup.py has started using a `cfdb-card` class, so every Today card rule now "
        "reaches it — re-scope them before this lands")
    assert "identity.player_row" in MATCHUP, (
        "if Matchup stopped calling the shared row this guard is testing nothing (R-760)")
