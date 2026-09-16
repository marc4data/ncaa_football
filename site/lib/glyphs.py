"""The marks two pages draw for the same three facts — ONE producer, not two.

🚨 THE ARGUMENT FOR THIS MODULE IS `distribution.py`'s OWN, AND IT IS THE REASON B114 DREW ITS BOX
PLOTS FROM A SHARED RENDERER RATHER THAN WRITING SVG: *"two renderers drift, and the day they
disagree the reader cannot tell which is lying."* Marc asked for *"the same Matchup and outcome
glyphs as on the Schedule page"* on Today — **and "the same" means the same PRODUCER.** A copy is
the same on the day it is made and on no day after.

---

## 🚨 THIS MODULE RETURNS MARKS. IT DOES NOT RETURN HTML. HERE IS WHY.

**The question was put as an open one** — should the shared thing be the mark, or finished markup?
**The two functions being moved answer it themselves, and they answer it the same way.**

    _winner_glyph   returned  <div style='text-align:center;font-size:1.4rem;line-height:1.1;
                                          opacity:.75'>◀</div>
    _outlook_glyph  returned  <span title='…' style='color:…;font-size:.8rem'>●</span>

⚠️ **NEITHER OF THOSE WRAPPERS IS ABOUT THE FACT. Both are about Matchup's layout.** The first is a
**block-level, centred, 1.4rem div** — that is the geometry of the scoreboard gap between two
scores, and it is meaningless in a table cell. The second's `.8rem` is the size of Matchup's legend
block. **Marc's Today request puts these glyphs in a Commentary CELL, above an ESPN link.** A cell
that inherited a centred 1.4rem block would be broken, and a caller that worked around it would be
writing the second implementation this module exists to prevent.

✅ **SO WHAT IS SHARED IS WHAT MUST NOT DIVERGE: the glyph, the colour, and the meaning.** What is
not shared is the size, the wrapper and the alignment, because those are the page's and always
were. **`render()` is offered for the common case; a page that needs a different footprint composes
the `Mark` itself and is still drawing the same mark.**

⚠️ **AND THE INVARIANT IS THEREFORE TESTABLE IN A WAY THE OLD SHAPE WAS NOT.** Two pages can now be
asserted to draw the same GLYPH for the same fact without asserting they use the same CSS — which
they must not.

---

## 🚨 AND IT IS AN INVENTORY, BECAUSE A LEGEND HAS TO BE ABLE TO WALK IT

`schedule.py` already solved the legend and its solution is a constraint on this module. R-178:
*"`_legend_key` calls `_indicator` — so the legend cannot draw a mark the row does not."* That
worked because `LEGEND_GROUPS` is an **enumerable inventory** the completeness tests walk, not a
hand-written list of swatches.

⚠️ **Marc's *"Need the legend button to help with the icons"* is that pattern again, and it only
works if the legend and the row share a producer.** So every mark this module can produce is
reachable from `entries()`, and `entries()` is built from the same tables the lookups use — **not a
parallel list.** A legend built from it cannot omit a mark a row can draw, and cannot invent one a
row cannot.

✅ **Today's legend is A143's to build. This module's job is to make building it a lookup rather
than a fourth pattern.**
"""
from typing import NamedTuple, Optional

import pandas as pd


class Mark(NamedTuple):
    """One drawable mark: what it is, what it looks like, and what it means.

    `key`    the stable identifier — the stored value, or the side that won
    `glyph`  the character to draw
    `color`  a CSS colour, or None where the page's own text colour is correct
    `title`  the hover text, and the legend's label
    """

    key: str
    glyph: str
    color: Optional[str]
    title: str


# ── the winner arrow ────────────────────────────────────────────────────────────────────────
#
# The glyph points OUTWARD, towards the score it belongs to: on Matchup it sits between the two
# scores, so the away score is to its left and the home score is to its right.
#
# ⚠️ THAT ORIENTATION IS A PROPERTY OF THE MARK AND NOT OF THE LAYOUT, WHICH IS WHY IT LIVES HERE.
# A page that stacks the two sides vertically would still want ◀ to mean *away* — the arrow names
# a side, and the side is the fact.
_WINNER = {
    "away": Mark("away", "◀", None, "away team won"),
    "home": Mark("home", "▶", None, "home team won"),
}


def winner(row, side: str) -> Optional[Mark]:
    """The arrow for `side`, and ONLY if that side won. `None` otherwise.

    🚨 ABSENT, NOT EMPTY, BEFORE KICKOFF — AND THIS RULE NOW HAS TWO CALLERS, WHICH MAKES IT MORE
    LOAD-BEARING RATHER THAN LESS. B075's rule for Matchup's after tab is the same rule here: **a
    post-game element on a pre-game page does not render a placeholder.** A tie draws nothing on
    either side, which is why this asks who WON rather than who did not lose.

    ⚠️ **A CALLER WHO DOES NOT KNOW THIS WILL RENDER A HOLE FOR A GAME THAT HAS NOT KICKED OFF.**
    `None` means *there is no mark here*, and the correct rendering of it is nothing at all — not
    an em dash, not a spacer, not a greyed arrow. **If a caller needs the COLUMN to keep its width
    on an unplayed game, that is the caller's layout problem (R-141) and it reserves the space
    itself; it does not ask this function for a placeholder mark.**

    ⚠️ AND `None` IS RETURNED FOR FOUR DIFFERENT REASONS — not completed, a missing score, a tie,
    and "this side did not win" — which are deliberately not distinguished. **A caller that needs
    to tell them apart is asking a different question and should read the row**, because a mark
    that meant "tie" would be a fourth mark this module would have to enumerate.
    """
    if not bool(row.get("is_completed")):
        return None
    home, away = row.get("home_points"), row.get("away_points")
    if home is None or away is None or pd.isna(home) or pd.isna(away):
        return None
    won = (side == "home" and home > away) or (side == "away" and away > home)
    return _WINNER[side] if won else None


# ── the matchup outlook ─────────────────────────────────────────────────────────────────────
#
# 🚨 R-722. MARC'S RULE, AND NONE OF IT IS COMPUTED HERE.
#
#     Green Circle: Gained < Allowed
#     Red Diamond:  Gained > Allowed and (Gained - Allowed) / Gained > .2
#     Yellow Circle: Gained > Allowed
#
# A119 published that as a column (`c89b516`) because the ratio is a DIVISION and a three-way
# bucketing is a CLASSIFICATION, and §4.2.1 puts both upstream. This maps a stored value to a look.
#
# 🚨 THE LITERAL IS `favorable`, AMERICAN SPELLING, AND IT IS NOT A DETAIL. A119 first shipped
# `favourable`, `test_no_dbt_description_uses_british_spelling` failed the build, and the value
# changed. A mapping keyed on `favourable` matches nothing and every mark silently disappears,
# which is why `test_the_MAPPING_KEYS_are_the_values_the_warehouse_actually_stores` reads the keys
# out of serving's own macro rather than trusting this table.
#
# ⚠️ SHAPE FIRST, COLOUR SECOND (AC-G.22). Marc's own rule gives the diamond to `challenging`, so
# the one state that says "this will be hard" is the one a greyscale reader can find by outline.
# Green and yellow are both circles and are separated by colour alone — the two tones are chosen
# for LUMINANCE distance rather than hue, and B116's greyscale render is the evidence.
_OUTLOOK_SHAPES = {("circle", True): "●", ("circle", False): "○",
                   ("diamond", True): "◆", ("diamond", False): "◇",
                   ("square", True): "■", ("square", False): "□"}

_OUTLOOK_MARKS = {
    "favorable": ("circle", "#1b6b3a", True),
    "contested": ("circle", "#c8a415", True),
    "challenging": ("diamond", "#b3261e", True),
}

# ⚠️ AN UNCLASSIFIED MARK DOES NOT BORROW ONE OF THE THREE LOOKS (AC-G.11). It is a HOLLOW SQUARE:
# neither of Marc's two shapes, unfilled, so it reads as "not classified" rather than as a fourth
# verdict — and it is legible in greyscale without its colour, which is the point of using a shape
# nothing else uses.
_UNCLASSIFIED = ("square", "#6b6b68", False)
UNCLASSIFIED_KEY = "unclassified"


def _look(value):
    """The (shape, colour, filled) triple for one stored value, or the unclassified look."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return _UNCLASSIFIED
    return _OUTLOOK_MARKS.get(str(value), _UNCLASSIFIED)


def outlook(value) -> Mark:
    """R-722's verdict as a `Mark`. Never `None` — an absent verdict is itself a mark.

    ⚠️ THE ASYMMETRY WITH `winner()` IS DELIBERATE AND IS THE DIFFERENCE BETWEEN THE TWO FACTS.
    *Nobody won yet* is an absence, so `winner()` returns `None` and the page draws nothing.
    *We hold no classification for this matchup* is a STATE the reader should see — it means the
    page looked — so it gets the hollow square rather than a hole.
    """
    shape, colour, filled = _look(value)
    known = shape != _UNCLASSIFIED[0] or filled != _UNCLASSIFIED[2]
    return Mark(str(value) if known and isinstance(value, str) else UNCLASSIFIED_KEY,
                _OUTLOOK_SHAPES[(shape, filled)], colour,
                str(value) if isinstance(value, str) else "not classified")


# ── the inventory a legend walks ────────────────────────────────────────────────────────────

def entries() -> list:
    """Every mark this module can produce, as `(group, [Mark, …])`.

    🚨 BUILT FROM THE SAME TABLES THE LOOKUPS USE, NEVER A PARALLEL LIST — which is R-178's whole
    property restated: **a legend cannot omit a mark a row can draw, and cannot invent one a row
    cannot.** `schedule.py`'s `_legend_key` earns that by delegating to `_indicator`; this earns it
    by enumerating the dictionaries `winner()` and `outlook()` read.

    ⚠️ IT IS ORDERED, AND THE ORDER IS MARC'S RULE READ TOP TO BOTTOM — favorable, contested,
    challenging — rather than the dictionary's insertion order by accident. The unclassified mark
    comes last because it is not one of his three.
    """
    return [
        ("Matchup", [outlook(value) for value in _OUTLOOK_MARKS] + [outlook(None)]),
        ("Outcome", [_WINNER["away"], _WINNER["home"]]),
    ]


def render(mark: Optional[Mark], size: str = "", extra: str = "") -> str:
    """One mark as a `<span>` — the COMMON case, not the only one.

    ⚠️ A PAGE THAT NEEDS A DIFFERENT FOOTPRINT COMPOSES THE `Mark` ITSELF AND IS STILL DRAWING THE
    SAME MARK. That is the whole reason this module returns marks: Matchup's winner arrow is a
    centred 1.4rem block between two scores and Today's is a glyph in a table cell, and neither
    wrapper is a fact about who won.

    🚨 `None` RENDERS AS THE EMPTY STRING, WHICH IS `winner()`'s ABSENT-NOT-EMPTY RULE MADE HARD TO
    GET WRONG. A caller that forwards `None` here gets nothing, rather than a placeholder.
    """
    if mark is None:
        return ""
    import html as _html
    style = ";".join(bit for bit in (
        f"color:{mark.color}" if mark.color else "", size) if bit)
    return (f"<span title='{_html.escape(mark.title)}'"
            + (f" style='{style}'" if style else "")
            + (f" class='{extra}'" if extra else "")
            + f">{mark.glyph}</span>")
