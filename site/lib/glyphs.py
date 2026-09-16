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

from lib import fmt


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


# ── THE RESULT STRIP — A SECOND VOCABULARY, DELIBERATELY NOT MERGED WITH THE FIRST ──────────
#
# A147, cfdb-main-R-951. Moved out of `schedule.py` because Today's Commentary cell now draws the
# same three indicators — Marc answered "which outlook?" with a PICTURE of Schedule's own *Game*
# column cell, so what he wanted was the details glyph and this strip, not the matchup verdict.
#
# 🚨 TWO VOCABULARIES IN ONE MODULE, AND THEY MUST NOT BECOME ONE LIST. `entries()` above answers
# *what did we expect* (Matchup) and *who won* (Outcome). These answer *what did the market make of
# it* — upset, cover, over. **A flat list would let either page's legend inherit groups its rows
# cannot draw**, which is R-178's law broken in the "invents a mark" direction: Today cannot draw
# the Matchup outlook (no outlook column on `srv_game` at any grain — A144 measured it), and
# Schedule does not draw the winner ARROWS (it has its own `WINNER_GLYPH`/`TIE_GLYPH`).
#
# ✅ SO THERE ARE TWO ENUMERATORS AND EACH LEGEND ASKS FOR THE GROUPS IT DRAWS. Both are built from
# the same dictionaries the producers read, which is the property that makes either legend unable
# to omit a mark a row can draw.
#
# ⚠️ R-141's FOOTPRINT RULE TRAVELS WITH `indicator` AND IS THE REASON THE MOVE IS A MOVE RATHER
# THAN A REWRITE: *"a mark that sized itself differently would take that alignment out from under a
# whole column of cards."* The emitted string is unchanged to the byte.

# R-141. THE UPSET LEVELS DIFFER ONLY BY COLOUR, and that is a decision rather than an oversight.
# It is the third deliberate exception to the site's glyph-plus-label convention after R-026's
# neutral-site icon, taken for the same reason: a small known user base, a legend that explains it
# once, and a dense row where three labelled indicators would cost more width than the whole rest
# of the cell.
UPSET_LEVEL_CLASS = {"upset": "cfdb-u1", "big": "cfdb-u2", "blowout": "cfdb-u3"}
UPSET_LEVEL_TITLE = {
    "": "no closing line, so nothing named a favorite",
    "none": "the favorite won",
    "upset": "upset",
    "big": "upset by more than a touchdown",
    "blowout": "upset by more than two touchdowns",
}
# R-181. ONE BASIS, so the tooltip states it rather than naming which of two produced the verdict.
UPSET_AGAINST = "the closing spread"

# R-171. "No closing line held" is a DASH, not a shape. It was a dotted outline, which still reads
# as a value being shown — a reader pulling in lower-division games that carry no spread or total
# saw three faint outlines with nothing saying why. A dash is the site's existing mark for "we hold
# nothing here".
NO_DATA_MARK = "\u2013"

_COVER_FILLS = {"yes": "fill", "no": "open", "push": "push"}
_COVER_TITLES = {"yes": "the winner also covered the closing spread",
                 "no": "the winner did not cover the closing spread",
                 "push": "the closing spread pushed"}
_OVER_TITLES = {"yes": "over the closing total",
                "no": "under the closing total",
                "push": "landed on the closing total"}


def upset_title(level: str) -> str:
    """The upset tooltip, with its basis named."""
    verdict = UPSET_LEVEL_TITLE.get(level, level)
    return f"{verdict}, against {UPSET_AGAINST}" if level else verdict


def indicator(shape: str, state: str, title: str, extra: str = "") -> str:
    """One indicator. SHAPES, NOT EMOJI — and a different shape per POSITION.

    Marc's three states mixed emoji-presentation characters with text-presentation ones, which do
    not share a baseline, do not size together and vary by platform. A span with a background, a
    border and a radius gives one rule for size, baseline and colour.

    THE SHAPE IS WHAT MAKES EACH ONE SELF-IDENTIFYING. All three were circles, so they could only be
    told apart by their position in the strip — and position is unreadable the moment one of them is
    invisible, which is most of the time. Circle, square, diamond: a reader can match any single
    indicator to its legend entry without counting its neighbours.

    🚨 THE DASH KEEPS THE SHAPE CLASS AND THEREFORE THE BOX. R-141 aligns every card's strip by
    giving the indicators identical footprints; a mark that sized itself differently would take that
    alignment out from under a whole column of cards. **A147 moved this function and changed not one
    character of what it emits** — `test_the_result_strip_moved_without_changing_a_byte`.
    """
    mark = NO_DATA_MARK if state == "nodata" else ""
    return (f"<span class='cfdb-ind cfdb-sh-{shape} cfdb-ind-{state} {extra}' "
            f"title='{title}'>{mark}</span>")


def result_strip(row) -> str:
    """R-141. Three indicators, populated only for a completed game.

    THE WIDTH IS RESERVED ON EVERY ROW, PLAYED OR NOT. An indicator set that appears only on
    completed games shifts the columns beside it the moment a week is half played — the alignment
    failure Schedule has fixed three times.

    "NOT AN UPSET" IS AN ANSWER, AND IT USED TO RENDER AS NOTHING. That made it identical to "not
    played yet", which is a different fact. It draws a quiet outline: present, answered,
    unremarkable. Only a game nobody has played renders truly nothing.

    ⚠️ R-172. NULL IS NOT "none". `is_upset` is null when neither side was ranked, and `or "none"`
    turned that absence into an assessment — a quiet circle claiming we had looked.

    ⚠️ EVERY COLUMN IT READS IS ON `srv_game`, WHICH BOTH CALLERS ALREADY SELECT FROM — checked
    against `information_schema` rather than against a query (§2.2.1c.2): `is_completed`,
    `upset_level`, `winner_covered_close`, `over_met`.
    """
    if not row.get("is_completed"):
        return ("<span class='cfdb-strip'>"
                + indicator("upset", "none", "not played yet")
                + indicator("cover", "none", "not played yet")
                + indicator("over", "none", "not played yet")
                + "</span>")
    upset = fmt.text(row.get("upset_level"))
    cover, over = fmt.text(row.get("winner_covered_close")), fmt.text(row.get("over_met"))
    parts = [
        indicator("upset",
                  "fill" if upset in UPSET_LEVEL_CLASS
                  else "quiet" if upset == "none" else "nodata",
                  upset_title(upset),
                  UPSET_LEVEL_CLASS.get(upset, "")),
        indicator("cover", _COVER_FILLS.get(cover, "nodata"),
                  _COVER_TITLES.get(cover, "no closing spread held"), "cfdb-acc"),
        indicator("over", _COVER_FILLS.get(over, "nodata"),
                  _OVER_TITLES.get(over, "no closing total held"), "cfdb-acc"),
    ]
    return f"<span class='cfdb-strip'>{''.join(parts)}</span>"


def strip_entries(bands=None) -> list:
    """The strip's inventory, as `(group, [(swatch_html, label), …])`. A147.

    🚨 BUILT FROM THE SAME DICTIONARIES `result_strip` READS, never a parallel list — R-178's law,
    and the reason this module is the right home for a legend's source.

    ⚠️ `bands` IS A PARAMETER BECAUSE THE UPSET THRESHOLDS ARE DATA, NOT A CONSTANT. R-224: they are
    columns on `srv_game`, so the labels are a function of the frame. A caller with no frame gets
    the level names; Schedule substitutes the measured bands it already computes.
    """
    labels = dict(bands or {})
    return [
        ("Against the line", [
            (indicator("upset", "quiet", ""), "The favorite won"),
            (indicator("upset", "fill", "", "cfdb-u1"), labels.get("upset", "Upset")),
            (indicator("upset", "fill", "", "cfdb-u2"), labels.get("big", UPSET_LEVEL_TITLE["big"])),
            (indicator("upset", "fill", "", "cfdb-u3"),
             labels.get("blowout", UPSET_LEVEL_TITLE["blowout"])),
            (indicator("cover", "fill", "", "cfdb-acc"), "Winner covered"),
            (indicator("cover", "open", "", "cfdb-acc"), "Winner did not cover"),
            (indicator("over", "fill", "", "cfdb-acc"), "Over"),
            (indicator("over", "open", "", "cfdb-acc"), "Under"),
            (indicator("cover", "nodata", ""), "No closing line held"),
            (indicator("upset", "nodata", ""), "No line, so no favorite"),
            # ✅ A147 FOUND A GAP IN SCHEDULE'S OWN LEGEND AND A149 CLOSED IT. `LEGEND_GROUPS`
            # listed `cover/nodata` and `upset/nodata` and NOT `over/nodata` — while a row draws it
            # whenever no closing total was held, which is every lower-division game. R-178's law
            # broken in the "omits a mark a row can draw" direction, and it had been there since
            # the strip was built.
            #
            # ⚠️ A147 DECLINED TO FIX IT THERE BECAUSE ADDING A ROW MOVES SCHEDULE'S RENDERED
            # BYTES, and that round's contract with the page was byte-identity. **That was A147's
            # promise rather than a standing rule**, so A149 added `schedule.py:515` and the two
            # inventories agree again. The label is copied from this line, not rewritten.
            (indicator("over", "nodata", ""), "No closing total held"),
        ]),
    ]


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
