"""`site/lib/glyphs.py` — the marks two pages draw for the same three facts.

🚨 THE MOVE THIS FILE GUARDS IS THE EASIEST THING IN THE WORLD TO TEST TAUTOLOGICALLY
(cfdb-wta-R-944). *"`outlook('favorable')` returns what `outlook('favorable')` returns"* passes on
any implementation, including a broken one. **Every assertion below is keyed on something OUTSIDE
the module** — the dbt macro that writes the stored values, the row data that decides who won, or
a property a legend needs — so a defect in the module cannot also move the thing it is measured
against.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import glyphs  # noqa: E402

_OUTLOOK_MACRO = (Path(__file__).resolve().parents[1] / "dbt" / "macros"
                  / "matchup_outlook.sql")


def _stored_values():
    """The verdicts the WAREHOUSE writes, read out of the macro that writes them."""
    text = _OUTLOOK_MACRO.read_text()
    return set(re.findall(r"then '([a-z_]+)'", text)) | set(re.findall(r"else '([a-z_]+)'", text))


def _row(completed=True, home=31, away=14):
    return pd.Series({"is_completed": completed, "home_points": home, "away_points": away})


# --- the absent-not-empty rule, which now has two callers ------------------------------------

@pytest.mark.parametrize("side", ("home", "away"))
def test_a_game_that_has_not_KICKED_OFF_has_NO_MARK_on_either_side(side):
    """🚨 ABSENT, NOT EMPTY — B075's rule, and the reason it is worth a test on the LIBRARY rather
    than on the page is that it now has two callers and the second one has not been written yet.

    ⚠️ **A caller who does not know this will render a hole for a game nobody has played.** `None`
    is the contract, and it is what `render()` turns into the empty string.
    """
    assert glyphs.winner(_row(completed=False, home=None, away=None), side) is None


@pytest.mark.parametrize("side", ("home", "away"))
def test_a_TIE_draws_NOTHING_on_either_side(side):
    """*"which is why this asks who WON rather than who did not lose"* — the docstring's own words.

    ⚠️ THE SYMMETRY IS THE ASSERTION. A tie is the one completed state where both sides must be
    empty, and an implementation that asked "did this side not lose" would mark BOTH.
    """
    assert glyphs.winner(_row(home=21, away=21), side) is None


def test_the_WINNER_gets_the_mark_and_the_LOSER_does_not():
    """The positive half, without which the two tests above pass on a function returning `None`."""
    home_won = _row(home=31, away=14)
    assert glyphs.winner(home_won, "home") is not None
    assert glyphs.winner(home_won, "away") is None
    away_won = _row(home=14, away=31)
    assert glyphs.winner(away_won, "away") is not None
    assert glyphs.winner(away_won, "home") is None


def test_the_ARROW_POINTS_AT_THE_SIDE_IT_NAMES():
    """🚨 THE ORIENTATION IS A PROPERTY OF THE MARK, NOT OF MATCHUP'S LAYOUT, WHICH IS WHY IT MOVED.

    On Matchup the glyph sits between the two scores, so it points outward — away to its left,
    home to its right. **A page that stacked the sides vertically would still want ◀ to mean
    *away*,** because the arrow names a side and the side is the fact.
    """
    assert glyphs.winner(_row(home=14, away=31), "away").glyph == "◀"
    assert glyphs.winner(_row(home=31, away=14), "home").glyph == "▶"


def test_a_MISSING_SCORE_on_a_completed_game_draws_nothing_rather_than_guessing():
    """AC-G.11. A completed game with no score is an absence, not a zero-zero tie."""
    for home, away in ((None, 14), (31, None), (float("nan"), 14)):
        assert glyphs.winner(_row(home=home, away=away), "home") is None
        assert glyphs.winner(_row(home=home, away=away), "away") is None


# --- the outlook marks, keyed on the warehouse rather than on the module ---------------------

def test_EVERY_VALUE_THE_WAREHOUSE_STORES_GETS_ITS_OWN_MARK():
    """🚨 KEYED ON THE MACRO THAT WRITES THE VALUES, NEVER ON THE MODULE'S OWN TABLE.

    A119 shipped `favourable`, CI rejected it, and the stored value became `favorable`. **A module
    keyed on a string the warehouse does not write matches nothing, every mark falls to the
    unclassified square, and the page still renders** — three verdicts quietly becoming one.

    ⚠️ AND *"ITS OWN"* IS THE HALF A PRESENCE CHECK WOULD MISS: three distinct marks, not three
    marks that happen to exist. Two verdicts sharing a glyph AND a colour is the same failure
    wearing a different shape.
    """
    stored = _stored_values()
    assert stored, "no literals found in the macro — this test's own subject has gone missing"
    marks = {value: glyphs.outlook(value) for value in stored}
    unclassified = glyphs.outlook(None)
    for value, mark in marks.items():
        assert (mark.glyph, mark.color) != (unclassified.glyph, unclassified.color), (
            f"{value!r} falls to the UNCLASSIFIED look — the module's table does not carry a key "
            f"the warehouse writes")
    looks = {(m.glyph, m.color) for m in marks.values()}
    assert len(looks) == len(stored), f"two stored verdicts share one look: {marks}"


def test_SHAPE_FIRST_COLOUR_SECOND_so_GREYSCALE_still_separates_the_hard_case():
    """AC-G.22, and it is Marc's own rule: the DIAMOND goes to `challenging`.

    **The one state that says "this will be hard" is the one a greyscale reader can find by
    outline alone.** The other two share a circle and are separated by luminance — B116's
    greyscale render is the evidence that the page survives it.
    """
    assert glyphs.outlook("challenging").glyph == "◆"
    assert glyphs.outlook("favorable").glyph == glyphs.outlook("contested").glyph == "●"

    def luma(hex_colour):
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    gap = abs(luma(glyphs.outlook("favorable").color)
              - luma(glyphs.outlook("contested").color))
    assert gap > 40, (
        f"the two circles are {gap:.0f} apart in luminance; in greyscale they are one mark and "
        f"Marc's rule loses a state")


def test_an_UNCLASSIFIED_verdict_does_not_BORROW_one_of_the_three_looks():
    """AC-G.11. *Not classified* is not a fourth verdict and must not wear one of the three."""
    stored = {glyphs.outlook(v).glyph for v in _stored_values()}
    for absent in (None, float("nan"), "favourable", "something_new"):
        mark = glyphs.outlook(absent)
        assert mark.glyph == "□", f"{absent!r} borrowed a verdict's shape: {mark}"
        assert mark.glyph not in stored, "the unclassified square is one of the three verdicts"
        assert mark.key == glyphs.UNCLASSIFIED_KEY


def test_an_UNCLASSIFIED_verdict_is_a_MARK_and_not_an_absence():
    """🚨 THE ASYMMETRY WITH `winner()`, ASSERTED SO IT CANNOT BE "TIDIED" INTO CONSISTENCY.

    *Nobody won yet* is an absence — `winner()` returns `None` and the page draws nothing.
    *We hold no classification* is a STATE the reader should see, because it means the page
    looked. **Making these two agree would delete one of the facts.**
    """
    assert glyphs.winner(_row(completed=False, home=None, away=None), "home") is None
    assert glyphs.outlook(None) is not None


# --- the property a legend needs (R-178) ----------------------------------------------------

def test_A_LEGEND_CAN_BE_BUILT_FROM_THE_MODULE_AND_OMITS_NOTHING_A_ROW_CAN_DRAW():
    """🚨 R-178's PROPERTY, DEMONSTRATED BY BUILDING ONE RATHER THAN ASSERTED.

    `schedule.py` earns it by delegating: *"`_legend_key` calls `_indicator` — so the legend cannot
    draw a mark the row does not."* ✅ **This module earns it by enumeration**, and this test is the
    demonstration Marc's *"Need the legend button to help with the icons"* depends on.

    ⚠️ THE EXPECTED SET IS BUILT THE WAY A ROW BUILDS ITS MARKS — by calling `outlook()` on every
    value the WAREHOUSE stores and `winner()` on real rows — **never by reading `entries()` and
    comparing it with itself.** That is the tautology cfdb-wta-R-944 warns about, and it is what
    makes this test able to fail.
    """
    drawable = {glyphs.outlook(value) for value in _stored_values()}
    drawable.add(glyphs.outlook(None))
    drawable.add(glyphs.winner(_row(home=31, away=14), "home"))
    drawable.add(glyphs.winner(_row(home=14, away=31), "away"))

    legend = {mark for _group, marks in glyphs.entries() for mark in marks}

    missing = drawable - legend
    assert not missing, (
        f"a row can draw {sorted(m.key for m in missing)} and the legend does not list it — "
        f"a reader meets a mark the legend cannot explain")
    invented = legend - drawable
    assert not invented, (
        f"the legend lists {sorted(m.key for m in invented)}, which no row can draw — "
        f"a legend entry for a mark that never appears is decoration (R-762)")


def test_THE_LEGEND_IS_GROUPED_AND_LABELLED_so_a_reader_can_use_it():
    """A legend is a list of marks WITH THEIR MEANINGS, or it explains nothing.

    ⚠️ AND EVERY ENTRY MUST CARRY A TITLE. A swatch with an empty label is R-178's own defect —
    *"the two entries were not faint. They were absent."*
    """
    groups = glyphs.entries()
    assert [group for group, _marks in groups] == ["Matchup", "Outcome"]
    for group, marks in groups:
        assert marks, f"the {group} group is empty"
        for mark in marks:
            assert mark.title.strip(), f"a {group} entry has no label: {mark}"
            assert mark.glyph.strip(), f"a {group} entry has no glyph: {mark}"


# --- what `render` is for, and what it deliberately is not -----------------------------------

def test_RENDER_turns_an_ABSENT_MARK_into_NOTHING_not_a_placeholder():
    """🚨 THE ABSENT-NOT-EMPTY RULE MADE HARD TO GET WRONG. A caller that forwards `None` gets the
    empty string, not a spacer, not an em dash."""
    assert glyphs.render(None) == ""


def test_RENDER_carries_the_MEANING_and_lets_the_PAGE_own_the_SIZE():
    """🚨 THE MARKS-NOT-HTML DECISION, ASSERTED.

    The shared thing is the glyph, the colour and the meaning. **The size is the page's** — Matchup
    draws the outlook at `.8rem` inside its legend block and Today will draw it in a table cell —
    so `render` must not impose one, and two calls differing only in size must still be the same
    mark.
    """
    mark = glyphs.outlook("favorable")
    bare, sized = glyphs.render(mark), glyphs.render(mark, size="font-size:1.2rem")
    assert "font-size" not in bare, f"render imposes a size on a caller that asked for none: {bare}"
    assert "font-size:1.2rem" in sized
    for drawn in (bare, sized):
        assert mark.glyph in drawn and mark.color in drawn and mark.title in drawn


def test_the_TITLE_IS_ESCAPED_because_it_is_a_stored_value():
    """The verdict reaches the page from the warehouse, and an unmapped one is echoed verbatim."""
    drawn = glyphs.render(glyphs.Mark("k", "●", None, "a <b>bold</b> claim"))
    assert "<b>" not in drawn and "&lt;b&gt;" in drawn
