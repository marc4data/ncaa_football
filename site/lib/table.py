"""One table renderer, so eighteen pages format numbers the same way.

Formatting only. Every value arrives already computed — this decides how it looks, never
what it is (G-3). A column spec is declarative so a page says what a column MEANS and the
renderer decides precision, alignment and chip treatment from that.
"""
import hashlib
import html
import re
from typing import Callable, List, Optional

import pandas as pd
import streamlit as st

from lib import chips, fmt, identity, params


# ── A208 (cfdb-main-R-2262, cfdb-main-R-2263): the shared scroll affordance ───────────────
#
# 🚨 A TABLE THAT SCROLLS SIDEWAYS AND DOES NOT SAY SO IS A DIFFERENT DEFECT FROM ONE THAT
# CLIPS, AND A WORSE ONE TO SHIP (AC-G.11). A203 fixed the distance table, A207 fixed the
# SLATE, and neither generalised; this is the third instance of one class in five rounds, so
# the mechanism lives with the wrapper every wide table already uses.
#
# 📊 THE FOUR `.cfdb-scroll` WRAPPERS ON THIS SITE, enumerated before anything moved:
#
#     Scores     the results table          `scores.py` -> render(scroll=True)   px layout
#     Today      Most Exciting              `today.py`  -> render(scroll=True)   px layout
#     Today      Furthest from the median   `today.py`  hand-built               _FAR_MIN_PX
#     Today      the SLATE, one per day     `today.py`  hand-built               _SLATE_MIN_PX
#
# ⚠️ AND SCHEDULE'S LIST IS NOT ONE OF THEM, though two shipped comments said it was. It calls
# `render` without `scroll=True` and emits no wrapper at all.
#
# 🚨 THE NOTE IS EMITTED ONLY WHERE THE BOUNDARY IS KNOWN. A caller whose columns are not all
# fixed pixels cannot say how wide its table wants to be, and a guessed boundary is exactly
# how a note appears above a table with nothing past its edge — which teaches readers to
# ignore it. `scroll_minimum` returns None there and no note is drawn.
SCROLL_NOTE = "\u2194 Scroll the table sideways to see the rest of the row."


def scroll_minimum(layout: Optional[List[str]]) -> Optional[int]:
    """How wide this table wants to be, or None when it cannot be known.

    ⚠️ ONLY AN ALL-PIXEL LAYOUT HAS AN ANSWER. A percentage layout is a share of whatever it
    is given, so it has no intrinsic width to compare a container against, and `auto` is
    content-driven and settled by the browser. Both return None, and the caller draws no note.

    🚨 THIS IS A LOWER BOUND ON THE DRAWN WIDTH, NOT THE DRAWN WIDTH, AND THE DIRECTION IS THE
    POINT. `table-layout:fixed` still lets a column exceed its declared width when its header's
    min-content is wider, so a table can draw wider than the sum of its colgroup. 📊 Measured in
    Chromium at 1440 with the sidebar open:

        Most Exciting   declared 1264   drawn 1272   +8     WIN PROBABILITY wants 244.6 of 238
        Scores          declared 1637   drawn 1752   +115   six 68px columns want up to 109.2
        the SLATE        declared 940   drawn  940   0      `table-layout:fixed` plus a colgroup
        distance table   declared 320   drawn  320   0

    ✅ SO THE NOTE CAN BE ABSENT WHILE A LITTLE IS PAST THE EDGE, AND CAN NEVER BE PRESENT WHEN
    NOTHING IS — because `shown` implies `container < declared <= drawn`. ⚠️ That is the
    direction to fail in: a note above a table with nothing hidden teaches a reader to ignore
    every note, which costs more than the few pixels it would have announced. 📊 And the band is
    unreachable in practice on both: Scores' container is 980 at a 1440 viewport, so it would
    take roughly a 2,200px viewport with the sidebar collapsed to land between 1637 and 1751.

    ⚠️ THE SCORES GAP IS A SEPARATE DEFECT AND IT IS NOT THIS FUNCTION'S. `column_layout` sizes
    those columns without their header labels (`seed_from_label=False`), which is deliberate for
    density — and A191 already measured that a header's drawn width is not what a naive
    measurement says. Filed as cfdb-main-R-2266; fixing it changes what Scores' columns look
    like, which is a round of its own.
    """
    if not layout or not all(str(w).endswith("px") for w in layout):
        return None
    try:
        return int(round(sum(float(str(w)[:-2]) for w in layout)))
    except ValueError:
        return None


def scroll_note(min_px: int, *, show_at: Optional[int] = None, lead: str = "") -> str:
    """The note, plus the `@container` rules that reveal it at this table's boundary.

    🚨 A209: `show_at` EXISTS BECAUSE ONE LINE CAN CARRY TWO FACTS THAT APPEAR AT DIFFERENT
    WIDTHS, AND BOTH HAVE TO BE TRUE WHERE THEY APPEAR (AC-G.11).

    The SLATE puts two columns away below 940 and, having done so, does not overflow until 820
    — so between those two widths the reader must be told about the columns and must NOT be
    told the row scrolls, because it does not. ⚠️ Two separate notes would be two sentences
    where one belongs; a single sentence with both clauses always on would be false at one of
    the two widths. **So the note element appears at `show_at` and the scroll CLAUSE inside it
    appears at `min_px`.**

    ✅ WITH `show_at` OMITTED THE TWO BOUNDARIES COINCIDE and the rendered line is exactly what
    A208 shipped, which is what the other three wrappers get.

    🚨 THE RULE IS GENERATED BECAUSE THE BOUNDARY IS PER-TABLE. A container query cannot read
    a custom property in its condition — `@container (max-width: var(--x))` is not a thing —
    so four tables with four minimums need four rules, and the number that produces them is
    the table's own. `[data-min]` keys the note to the rule that belongs to it, so two boxes
    on one page with different boundaries do not reveal each other.

    ⚠️ HIDDEN BY DEFAULT. `.cfdb-scrollnote` carries `display:none` in the stylesheet and only
    the query turns it on: with no container-query support the reader gets a table whose note
    never appears — mildly under-informative — rather than one that is always on. The
    stylesheet's comment carries the rest of the reasoning.
    """
    at = show_at or min_px
    return (f"<style>@container (max-width:{at - 1}px)"
            f"{{.cfdb-scrollnote[data-min='{at}']{{display:flex}}}}"
            f"@container (max-width:{min_px - 1}px)"
            f"{{.cfdb-scrollnote[data-min='{at}'] .cfdb-scrollnote-scroll"
            f"{{display:inline}}}}</style>"
            f"<div class='cfdb-scrollnote' data-min='{at}'>{lead}"
            f"<span class='cfdb-scrollnote-scroll'>{SCROLL_NOTE}</span></div>")


def scroll_box(markup: str, min_px: Optional[int]) -> str:
    """Wrap markup in the scroller, with the note when the boundary is known."""
    scroller = f"<div class='cfdb-scroll'>{markup}</div>"
    if not min_px:
        return scroller
    return f"<div class='cfdb-scrollbox'>{scroll_note(min_px)}{scroller}</div>"


class Col:
    """One column: where it comes from, what it is, and how it should read."""

    def __init__(self, field: str, label: str, kind: str = "text",
                 dp: Optional[int] = None, width: Optional[str] = None,
                 render: Optional[Callable] = None,
                 link: Optional[Callable] = None,
                 opens: Optional[str] = None,
                 title: Optional[str] = None):
        self.field, self.label, self.kind = field, label, kind
        self.dp, self.width, self.render = dp, width, render
        # 🚨 A189 (cfdb-main-R-1927). A HEADER TOOLTIP, BECAUSE A CAPTION WAS THE WRONG SHAPE.
        #
        # > **MARC:** *"The paragraph about methodology should be removed below the table."*
        #
        # ⚠️ REMOVING IT TAKES SOMETHING WITH IT: `4th qtr`, `OT` and `Game` are only legible
        # as LEAD CHANGES because the caption said so. A one-line `title` puts that where the
        # reader already is — on the column — instead of a paragraph under the table.
        # **One short line per column. Anything longer belongs in the section caption above.**
        self.title = title
        # ── A178 (cfdb-main-R-1850): WHICH WAY THIS COLUMN OPENS ────────────────────────────
        #
        # > MARC, v10: "When I choose a column header to force a sort, it shift to sort asc,
        # > but end-user will generally want to see the best performers for the metric (desc).
        # > Can you make desc the first sort."
        #
        # 🚨 HIS REASON IS RIGHT AND IT DOES NOT GENERALISE, WHICH IS WHY THIS IS PER COLUMN
        # AND NOT ONE CONSTANT. "The best performers" is `desc` for a yards column and `asc`
        # for a RANK, where 1 is best. `table.render` is the site's ONLY table producer —
        # Schedule, Scores, Standings, Rankings, every Team tab, every Matchup table and every
        # Leaderboard — so a global flip would put 136th on top of the Rankings page.
        #
        # 🚨 AND `kind` ALONE CANNOT DECIDE IT, WHICH WAS MEASURED RATHER THAN ASSUMED. Of the
        # 193 `Col` call sites on the site, FOUR ranks carry `kind="num"`: `ap_rank`,
        # `coaches_rank` and `committee_rank` on Rankings, and `tiebreak_rank` on Standings.
        # Defaulting `num` to `desc` and stopping there would have shipped exactly the defect
        # the paragraph above describes. Those four declare `opens="asc"` at their call sites.
        #
        # ⚠️ `opens` IS THE OVERRIDE, NOT THE RULE. Left unset a column takes the default for
        # its kind, so 75 measure columns get Marc's ask without 193 edits — and a column that
        # needs the other answer says so where a reader is already looking at it.
        self.opens = opens
        # A column-specific destination, which WINS over the row link for that cell.
        # AC-2.5 wants both on one row: the row goes to the game, the team name goes to the
        # team. Nested anchors are invalid HTML, so it has to be one or the other per cell.
        self.link = link

    def format(self, row) -> str:
        if self.render is not None:
            return self.render(row)
        value = row.get(self.field)
        if self.kind == "plain":
            # R-280. A NUMERIC LABEL: no decimal point and NO THOUSANDS SEPARATOR. A season
            # is 2025 and a game id is 401752817; a comma in either is a bug, and the
            # workbook has said so in a comment since R-216 while the page printed 2,025.
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return fmt.EM_DASH
            return f"{int(value)}"
        if self.kind == "num":
            return fmt.number(value, self.field, self.dp)
        if self.kind == "signed":
            return fmt.signed(value, self.field, self.dp)
        if self.kind == "datetime":
            return fmt.local_time(value)
        if self.kind == "time":
            return fmt.clock(value)
        if self.kind == "date":
            return fmt.day(value)
        if self.kind == "cover":
            return chips.cover_chip_html(value)
        if self.kind == "bool":
            return chips.chip_html("y", "Yes") if value else chips.chip_html("n", "No")
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return fmt.EM_DASH
        return str(value)

    @property
    def first_order(self) -> str:
        """The direction this column sorts in when it is clicked from cold.

        ⚠️ ONLY THE FIRST CLICK. Clicking the ALREADY-ACTIVE column still flips whatever it is
        showing — that toggle is what makes a header a control rather than a setting, and Marc
        asked for a better starting point, not for the toggle to go.
        """
        if self.opens in ("asc", "desc"):
            return self.opens
        # A measure: bigger is the interesting end. Everything else — a name, a date, a chip,
        # a display string — reads from the top down.
        return "desc" if self.kind in ("num", "signed") else "asc"

    @property
    def css(self) -> str:
        if self.kind in ("num", "signed", "plain"):
            return "cfdb-num"
        # R-103. A glyph column is neither a number nor prose. Right-aligning "☀ 71°F"
        # hung it off the right edge of its own header; left-aligning left it stranded
        # beside a wide neighbour. The kind carries the alignment so the caller does not
        # hand-write a class per cell.
        if self.kind == "center":
            return "cfdb-center"
        return ""


def table_key(columns: List[Col]) -> str:
    """A short, stable id for THIS table, derived from its own column shape.

    🚨 A189 (cfdb-main-R-1925). `?sort=` WAS PAGE-WIDE, SO ONE TABLE'S HEADER RE-SORTED ANOTHER.
    📊 Measured on Today, week 3: clicking **"Getting"** on *Biggest underdog covers* sets
    `?sort=spread`, and *Biggest upsets* — which has its own `spread` column and sits directly
    above — silently re-ordered from its stated ranking. Texas A&M at 84.1% fell from first to
    below Wyoming at 47.8%, while the caption still read *"ranked by how likely the market
    thought the loser was to win"*. **A panel contradicting its own caption is exactly the
    true-sounding-label defect §4.3 exists to stop.**

    ⚠️ THE ANCHOR CANNOT BE THE KEY, WHICH IS WHY THIS IS A HASH. `_recap_lists` passes the SAME
    anchor to both tables — they share a section heading — so keying on it would have left the
    two tables that actually collided still colliding. The COLUMN SHAPE is what differs.

    ⚠️ AND IT IS DERIVED, NOT DECLARED, so no caller has to remember it. A `table_key=` argument
    would be the opt-in this module already learned to distrust: `sortable=True` drew live links
    that sorted nothing in eleven views because the working behaviour was the thing you had to
    ask for (A141).

    Two tables with an identical column shape on one page share a key, and that is correct
    rather than a collision: sorting both the same way is what a reader asking for that sort
    would mean.
    """
    shape = "|".join(c.field or f"?{c.label}" for c in columns)
    return hashlib.sha1(shape.encode("utf-8")).hexdigest()[:6]


def split_sort(raw: Optional[str]) -> tuple:
    """`<key>.<field>` -> (key, field). A bare field -> (None, field).

    The bare form is what a hand-edited or pre-A189 link carries. It is honoured for the table
    that owns the field so an old bookmark still sorts something sensible, rather than being
    dropped silently (AC-G.11) — but it cannot be produced by any link this module draws.
    """
    if not raw:
        return None, None
    if "." in raw:
        key, _, field = raw.partition(".")
        return key, field
    return None, raw


def apply_sort(df: pd.DataFrame, columns: List[Col],
               default: Optional[str] = None, key: Optional[str] = None) -> pd.DataFrame:
    """Sort the frame by whichever column the URL asks for. AC-2.8.

    SORTING IS DISPLAY, and doing it here is not the thing AC-5.1 forbids. That rule is
    about business logic — a conference tiebreaker implemented in Python is a defect because
    the ordering is a DEFINITION that belongs in dbt. "Show me this table by attendance
    descending" is a reader rearranging what they were already given.

    Server-side rather than JavaScript, and that is the second time this pattern has paid:
    Streamlit strips event handlers, so a client-side sorter would render an arrow attached
    to nothing exactly as the row links did. A header that is an <a href> toggling a query
    param sorts, survives a reload, and can be sent to somebody.

    Applied BEFORE grouping so a grouped table sorts within each group and the groups
    themselves keep their own order — a day is still a day.
    """
    asked_key, field = split_sort(params.get("sort"))
    # 🚨 A189: A SORT ADDRESSED TO ANOTHER TABLE IS NOT THIS TABLE'S SORT. Before this, any
    # `?sort=` applied to every table on the page that happened to carry a column of that name.
    if asked_key is not None and key is not None and asked_key != key:
        field = None
    field = field or default
    if not field:
        return df
    if field not in df.columns:
        # A stale or hand-edited ?sort= names a column this table does not have. Ignore it
        # rather than raising: an unknown sort is noise, not a request (AC-G.11).
        return df
    # A178: with no `order` in the URL, the column's own opening direction decides — otherwise
    # a hand-edited or truncated link sorts one way while the header's arrow claims the other.
    # Every link this module BUILDS carries both, so this is the edge case, not the path.
    by_field = {c.field: c for c in columns if c.field}
    fallback = by_field[field].first_order if field in by_field else "asc"
    ascending = (params.get("order") or fallback) == "asc"
    # na_position last in both directions: a null is not the smallest value, it is the
    # absence of one, and burying them keeps the top of the table meaningful either way.
    return df.sort_values(field, ascending=ascending, na_position="last",
                          kind="mergesort")


def _tip(column: Col) -> str:
    """The header's `title` attribute, or nothing. A189 — see `Col.title`.

    🚨 A191 (cfdb-main-R-2009). THE VALUE IS ESCAPED, BECAUSE AN APOSTROPHE ENDED THE
    ATTRIBUTE AND SILENTLY TRUNCATED THE TOOLTIP.

    📊 A191 moved Most Exciting's caption into header tooltips, and the Win probability one
    begins *"The home side's win probability on every play…"*. Interpolated raw into
    `title='…'` the apostrophe CLOSES the attribute: the browser kept `The home side`, and
    the remaining 200 characters became stray markup inside the `<th>`.

    ⚠️ IT LOOKED LIKE A WORKING TOOLTIP, WHICH IS WHY IT NEEDS A GUARD RATHER THAN CAREFUL
    WORDING. Hovering the header showed a short sentence that reads as complete. Only reading
    the rendered attribute back showed the cut — the same shape as every other defect this
    round: an instrument that reports success on a truncated result.

    ⚠️ AND TEAM NAMES MAKE THIS UNAVOIDABLE RATHER THAN HYPOTHETICAL — "Saint Mary's (CA)",
    "East Texas A&M". `html.escape` handles the ampersand for the same reason.
    """
    title = getattr(column, "title", None)
    return f" title='{html.escape(str(title))}'" if title else ""


def _header_cell(column: Col, sortable: bool, freeze: str = "",
                 fields: Optional[set] = None, anchor: Optional[str] = None,
                 key: Optional[str] = None) -> str:
    """A header, and a sort toggle where the column has something to sort by.

    🚨 `fields` IS THE FRAME'S OWN COLUMNS, AND IT IS THE GENERAL FORM OF THE LIST BELOW — A141.
    That list is a hand-maintained proxy for *"this field is not in the frame, so `apply_sort`
    will drop it and the link will do nothing"*, and a hand-maintained list goes stale the day
    somebody adds a synthetic column. 📊 **A138 added two — `scoreboard` and `curve` — and
    measured on the running page, Looking Back was offering 41 sort links of which 12 named a
    field the frame does not have.** Asking the frame cannot go stale.

    ⚠️ THE LIST STAYS AS WELL, and it is not redundant: it also excludes fields that ARE in the
    frame but whose column renders something else entirely. Both tests have to pass, so this
    strictly removes dead links and can never add one.
    """
    if fields is not None and column.field and column.field not in fields:
        return (f"<th class='{column.css}{freeze}'{_tip(column)}>"
                f"{column.label}</th>")
    # A synthetic column has no field to sort by — "Spread · model" is two numbers in one
    # cell, and the details glyph is not data. Those render as plain headers rather than
    # as links that would do nothing.
    if not sortable or not column.field or column.field in ("details", "flag", "rank",
                                                            "team", "away", "home",
                                                            "record", "overall",
                                                            "conf_record", "winner",
                                                            "ats", "basis", "status",
                                                            "description", "market",
                                                            "result", "bucket",
                                                            # R-101/R-103. Both are synthetic
                                                            # fields with no column behind
                                                            # them, so a sort link on either
                                                            # renders an arrow and then does
                                                            # nothing — apply_sort drops an
                                                            # unknown field. "weather" has
                                                            # been offering that dead link
                                                            # since R-027 shipped.
                                                            "game", "weather",
                                                            "spread_and_model"):
        return (f"<th class='{column.css}{freeze}'{_tip(column)}>"
                f"{column.label}</th>")

    asked_key, asked_field = split_sort(params.get("sort"))
    order = params.get("order") or "asc"
    # A189: the arrow lights only when the sort is addressed to THIS table.
    is_active = (asked_field == column.field
                 and (asked_key is None or key is None or asked_key == key))
    # A178. Clicking the ACTIVE column flips it; clicking a NEW one opens the way that column
    # opens — `desc` for a measure, `asc` for a rank or a name. See `Col.first_order`.
    next_order = ("desc" if order == "asc" else "asc") if is_active else column.first_order
    arrow = ("▲" if order == "asc" else "▼") if is_active else "⇅"
    # A189: the link names the table as well as the column, so it cannot re-sort a neighbour.
    href = params.link_here(sort=f"{key}.{column.field}" if key else column.field,
                            order=next_order)
    # THE FRAGMENT IS APPENDED, NEVER BUILT INTO `link_here`. That function's job is the QUERY,
    # which is the linkable state; a fragment is a scroll position and is not state at all.
    if anchor:
        href = f"{href}#{anchor}"
    active = " cfdb-sorted" if is_active else ""
    return (f"<th class='{column.css}{active}{freeze}'{_tip(column)}>"
            f"<a class='cfdb-sort' href='{href}' target='_self'>{column.label}"
            f"<span class='cfdb-sort-arrow'>{arrow}</span></a></th>")


PIXELS_PER_CHARACTER = 8.5
MIN_COLUMN_PIXELS = 44
# Three lines of header is already a lot; past that the LABEL is the problem.
HEADER_LINE_CAP = 3


def header_lines(columns: List[Col], layout: List[str]) -> int:
    """How many lines the deepest header needs at these widths.

    Computed rather than chosen, for the reason R-217 computes it in the workbook: a
    hardcoded height fits today's labels and clips the next long one. Words are not broken,
    so the depth follows the longest WORD that has to fit, not the character count.
    """
    deepest = 1
    for column, width in zip(columns, layout):
        if not width.endswith("px"):
            continue
        # .78rem uppercase with .02em of tracking runs a little under 7px per character.
        capacity = max(int(int(width[:-2]) / 6.8) - 1, 1)
        line, used = 1, 0
        for word in str(column.label).split():
            need = len(word) + (1 if used else 0)
            if used and used + need > capacity:
                line, used = line + 1, len(word)
            else:
                used += need
        deepest = max(deepest, line)
    return min(deepest, HEADER_LINE_CAP)


def column_layout(df: pd.DataFrame, columns: List[Col],
                  unit: str = "%", seed_from_label: bool = True) -> List[str]:
    """Column widths computed ONCE over the whole dataset, for reuse across every group.

    F2-06, raised five times across two passes and by frequency the number one item in the
    feedback. When a page renders several tables of the same shape — Today and Schedule
    grouped by day, Teams grouped by conference — each group otherwise sizes itself to its
    own contents, so the same column is 90px in one block and 140px in the next and the page
    reads as ragged.

    Per-table autofit cannot fix that, because the whole problem is that each table only
    knows about itself. The layout has to be computed BEFORE grouping and handed to every
    group, which is why this returns a list of widths rather than styling anything.

    Widths are proportional rather than absolute: a percentage keeps the table responsive on
    a laptop, which is where Marc reads it, while still being identical across groups.
    """
    weights = []
    for column in columns:
        widest, has_image, has_record = 0, False, False
        has_big_glyph = has_strip = False
        for _, row in df.iterrows():
            rendered = str(column.format(row))
            # A LOGO IS WIDTH THE TEXT MEASURE CANNOT SEE. Stripping tags is right for a
            # chip, whose text IS its width, and wrong for an image, whose text is nothing
            # and whose box is 20px. Schedule's Away column was short by exactly a logo, so
            # "New Mexico State" pushed its record onto a second line.
            if "<img" in rendered or "cfdb-monogram" in rendered:
                has_image = True
            if "cfdb-team-record" in rendered:
                has_record = True
            # R-131 made these glyphs 1.3rem against a .9rem body, so two characters of
            # stripped text render about as wide as five. At 1280 the GAME header wrapped
            # because the column was sized for the text the glyphs are not.
            if "cfdb-details" in rendered or "cfdb-neutral" in rendered:
                has_big_glyph = True
            # R-141's indicators are EMPTY SPANS — pure CSS shapes with no text at all — so
            # stripping tags leaves literally nothing to measure. The fourth thing in this
            # function that is width the text cannot see, after the logo, the inline margins
            # and the oversized glyphs. Three dots plus their gaps and the separator run about
            # 60px, near enough eight characters.
            if "cfdb-strip" in rendered:
                has_strip = True
            # Strip tags before measuring — a chip is markup, not width.
            widest = max(widest, len(re.sub(r"<[^>]+>", "", rendered)))
        # NUMBERS ARE SET IN A MONOSPACE FACE and the label is not, so one character is not
        # one unit in both. `.cfdb-num` is ui-monospace at roughly 0.6em per character
        # against about 0.52em for the proportional face — near enough 1.15. Without it a
        # five-character "−10.2" was measured as though it were five characters of prose and
        # broke across two lines.
        if column.kind in ("num", "signed"):
            widest *= 1.15
        # THE ALLOWANCE COVERS THE LOGO AND THE MARGIN AFTER IT. 28px of image plus `.4rem`
        # of margin is about 34px, near enough six characters — measured at 1280, where the
        # 4-character version left the Away cell 21px short and "Kennesaw State" wrapped onto
        # two lines. Inline margins are invisible to a text measure and there are two of them
        # in a team cell, so the second is added below.
        if has_image:
            widest += 6
        if has_record:
            widest += 1
        if has_big_glyph:
            widest += 5
        if has_strip:
            widest += 8
        # AND THE HEADER IS NOT PROSE EITHER. `.cfdb-table th` is uppercased with .02em of
        # letter-spacing, so six characters of "Spread" occupy more than six characters of
        # body text. Without this the SPREAD header broke to "SPREA / D" the moment the two
        # corrections above gave its neighbours their honest share.
        # R-282. THE LABEL IS A FLOOR ONLY WHERE THE CALLER WANTS ONE.
        #
        # `max(label, data)` means a long header WIDENS its column instead of wrapping inside
        # it — precisely backwards from "increase the vertical size of the headers to get some
        # wordwrap and make the data fields more dense". Measured on Scores: Team and Opponent
        # 212px each, Conference 170, every one set by the label rather than by the data.
        #
        # R-217 already ruled on this for the WORKBOOK — "widths measured from the DATA, not
        # seeded with the header label, and the header row height computed from wrap depth" —
        # and the page, built second, did not inherit it. Not a new decision; the existing one,
        # applied to the other surface.
        #
        # The seventeen other callers keep the floor. Their tables fit on a screen, where a
        # wrapped header costs more than a wide column does.
        longest = max(len(str(column.label)) * 1.1, widest) if seed_from_label else widest
        # Clamped in both directions: a floor so a two-character header stays readable, a
        # ceiling so one long venue name does not take half the table.
        #
        # THEN A PADDING ALLOWANCE, WHICH THE FIRST VERSION LEFT OUT AND WHICH IS WHY NARROW
        # COLUMNS WRAPPED. Every cell carries .5rem of padding on each side — about two
        # characters' worth — and that cost is CONSTANT per column while these weights are
        # PROPORTIONAL. On a wide column it disappears into the rounding; on a six-character
        # one it is a fifth of the box. Schedule showed both failure modes at once: "SPREAD"
        # broke to "SPREA / D", and the score column rendered 30 as "3 / 0".
        #
        # Adding it before normalising is what makes the share reflect the box the browser
        # will actually need, and it redistributes toward the narrow columns, which are the
        # only ones that were ever short.
        #
        # The floor is 5 rather than 4 for the same reason R-100 exposed this: a numeric
        # column that reserves a marker holds a glyph plus its digits, and four characters
        # does not fit "▸30" once the padding is honest.
        weights.append(min(max(longest, 5), 34) + 3)
    if unit == "px":
        # PERCENTAGES CANNOT OVERFLOW, WHICH IS THE WHOLE PROBLEM (R-269).
        #
        # A percentage resolves against a container that is already constrained, so thirty-nine
        # columns do not spill past the viewport — they compress until every cell is
        # unreadable, and there is nothing to scroll because nothing is wider than the screen.
        # The MEASUREMENT above is right and is kept; only the unit has to change.
        #
        # The weights are in characters-plus-padding, so one constant converts them. 8.5px is
        # measured against `.cfdb-table`'s .9rem body text, and the floor keeps a two-character
        # column from collapsing to nothing once it is no longer sharing out a fixed total.
        return [f"{max(int(weight * PIXELS_PER_CHARACTER), MIN_COLUMN_PIXELS)}px"
                for weight in weights]
    total = sum(weights) or 1
    return [f"{100 * weight / total:.2f}%" for weight in weights]


def render(df: pd.DataFrame, columns: List[Col], caption: str = "",
           link_builder: Optional[Callable] = None, max_rows: int = 300,
           layout: Optional[List[str]] = None, sortable: bool = True,
           scroll: bool = False, sticky: int = 0,
           row_class: Optional[Callable] = None,
           header_height: Optional[int] = None,
           anchor: Optional[str] = None) -> None:
    """An HTML table, because Streamlit's dataframe cannot hold a chip or a link.

    AC-G.47: the table carries header semantics and a caption naming its source view.

    🚨 THIS FUNCTION APPLIES THE SORT IT DRAWS — A141, cfdb-main-R-948, AND IT DID NOT USED TO.
    `sortable=True` drew the header links; `apply_sort` was a SEPARATE call the view had to
    remember. 📊 ELEVEN OF SIXTEEN VIEWS DID NOT MAKE IT, and `today.py` — thirteen tables across
    nine calls — made it nowhere. Every header on those pages was a live-looking link that
    changed the URL, cost a full page reload and re-sorted nothing.

    Marc, three times under three different sections of his 2026-09-16 notes:

        "Column sort isn't working.  The whole page reloads and end-user has to scroll down
         to get to the same page s/he clicked from."

    ⚠️ THE DEFAULT WAS THE DEFECT, WHICH IS THE PART WORTH FIXING RATHER THAN THE THIRTEEN CALLS.
    A view opted OUT of drawing the links and had to opt IN to making them work: forgetting
    produced something that LIES rather than something inert. This repository had already
    written that lesson down — `params.py` on `?view=stacked`: *"the feature was inert and looked
    fine"* (R-043). Same class, eleven views wide.

    ✅ SO THE SORT MOVES INSIDE, AND THE VIEWS STOP CALLING `apply_sort` AT ALL. That is what
    makes a double sort IMPOSSIBLE rather than merely harmless: there is one call site.
    `test_no_view_applies_the_sort_itself` holds it there.

    ⚠️ AND A TABLE WITH FEWER THAN TWO ROWS DRAWS NO SORT LINKS. A control that cannot change
    anything is the dead-link class this round exists to end, and a per-view judgement about
    which tables are one-row would be a list that goes stale. The frame answers it every render.

    🚨 `sortable` IS TRI-STATE, AND THE THIRD STATE EXISTS BECAUSE ONE VIEW GENUINELY NEEDS THE
    SORTED FRAME BEFORE IT RENDERS:

        True         render applies the sort and draws the links. Every view but one.
        False        no links and no sort.
        "applied"    the caller has ALREADY sorted; draw the links, do not sort again.

    🚨 `anchor` IS THE SECOND HALF OF WHAT MARC REPORTED — *"the whole page reloads and end-user
    has to scroll down to get to the same page s/he clicked from."* A sort is a URL, deliberately
    (AC-G.18: a sorted view has to survive a reload and be sendable), so the reload is the design
    and the LOST POSITION is the defect.

    📊 MEASURED IN A BROWSER AGAINST THE REAL PAGE, because Cowork had not verified it and it is
    not obvious — this page does not scroll the document at all, it scrolls Streamlit's own
    `stMain` container, so a fragment might well have been inert:

        #leaderboards on a COLD load        stMain.scrollTop stays 0    ← the fragment does nothing
        scrollIntoView() once rendered      stMain.scrollTop 5654       ← the container IS scrollable
        a SORT navigation carrying it       stMain.scrollTop 3000 -> 5654  ✅ it works

    ✅ AND THE CASE THAT WORKS IS EXACTLY THE ONE MARC IS IN. A sort click is a same-document
    query change on an app that is already loaded, so the DOM survives and the browser applies
    the fragment to an element that exists. A cold load with a fragment does not, because the
    body arrives over the websocket after the browser has already looked — **so this is a
    position restore, not a linkable deep link, and it is not sold as one.**

    ⚠️ THE ANCHOR IS STREAMLIT'S OWN HEADING ID, not one this module invents: `st.subheader`
    emits `<h3 id="most-exciting">`, and the ids were read off the rendered page rather than
    assumed. A view passes the slug of the heading its table sits under.

    ⚠️ `scores.py` IS THE ONE, AND IT IS NOT A STYLE PREFERENCE. It computes its row cap with
    `_pairs_only`, which must not cut INSIDE a game's two rows — a question about the sorted
    order — and it measures its column widths from the same frame. Sorting after that would
    invalidate the cap it just computed. ✅ `test_only_scores_applies_its_own_sort` is what keeps
    the third state from spreading: a view that adds an `apply_sort` call has to justify it.

    ROWS ARE LINKED WITH REAL ANCHORS, and that is a fix rather than a style choice. This
    used to put `onclick="window.location=..."` on the <tr>. Streamlit's markdown sanitiser
    strips event handlers, so every row rendered with a pointer cursor and did nothing —
    the whole site was a set of termini, which is exactly what Marc reported.

    An onclick would have failed AC-G.13 even if it had survived: the criterion is that
    middle-click or copy-link on any row yields a working URL, and a JavaScript handler
    gives neither. An <a href> gives both for free, and navigates by writing query params
    because that is what the href contains.

    Every CELL carries the anchor rather than the row, because <a> cannot wrap <tr>. The
    anchor is display:block so the whole cell is the target, which makes the row clickable
    in effect while staying valid HTML that a browser can middle-click.
    """
    # A189: this table's own sort identity, derived from its column shape. See `table_key`.
    key = table_key(columns)

    # 🚨 THE SORT, APPLIED HERE AND NOWHERE ELSE. See the docstring.
    #
    # ⚠️ ORDER MATTERS BETWEEN THESE TWO LINES: the links are suppressed on the SAME condition
    # that suppresses the sort, so a header can never offer something the table will not do.
    if sortable is True and len(df) > 1:
        df = apply_sort(df, columns, key=key)
    elif len(df) < 2:
        sortable = False

    # A colgroup rather than per-cell widths: one declaration the browser applies to the
    # whole table, and identical markup in every group when `layout` is shared.
    colgroup = ("<colgroup>"
                + "".join(f"<col style='width:{width}'>" for width in layout)
                + "</colgroup>") if layout else ""

    # WHERE EACH FROZEN COLUMN HAS TO SIT, IN PIXELS (R-269).
    #
    # `position:sticky` cannot go on a <col> — the browser ignores it there — so it goes on
    # every th and td of the frozen columns, and each needs its own `left` offset: the sum of
    # the widths to its left. That is only computable when the layout is in px, which is the
    # second reason percentages had to go.
    #
    # `sticky` is silently ignored without a px layout rather than half-applied. A sticky
    # column with no left offset pins to 0 and stacks all of them on top of each other, which
    # looks like a rendering bug and is very hard to read back to this line.
    offsets, edge = {}, -1
    if scroll and sticky and layout and all(w.endswith("px") for w in layout[:sticky]):
        running = 0
        for index in range(min(sticky, len(layout))):
            offsets[index] = running
            running += int(layout[index][:-2])
        edge = min(sticky, len(layout)) - 1

    def freeze(index: int) -> str:
        if index not in offsets:
            return ""
        css = " cfdb-sticky" + (" cfdb-sticky-edge" if index == edge else "")
        return f"{css}' style='left:{offsets[index]}px"

    # ⚠️ THE FRAME'S OWN COLUMNS, SO A HEADER CANNOT OFFER A SORT THE FRAME CANNOT SATISFY.
    fields = set(df.columns)
    head = "".join(_header_cell(c, sortable, freeze(i), fields, anchor, key)
                   for i, c in enumerate(columns))
    body = []
    for _, row in df.head(max_rows).iterrows():
        row_href = link_builder(row) if link_builder else None
        cells = []
        for index, column in enumerate(columns):
            content = column.format(row)
            href = column.link(row) if column.link else row_href
            css = "cfdb-cell-link" + (" cfdb-cell-link-alt" if column.link else "")
            if href:
                content = f"<a class='{css}' href='{href}' target='_self'>{content}</a>"
            cells.append(f"<td class='{column.css}{freeze(index)}'>{content}</td>")
        joined = "".join(cells)
        # An extra class per row, for a caller that bands on something only it can know —
        # Scores shades alternating RUNS of one game, which is a property of the rendered
        # order and not of the row.
        extra = (row_class(row) or "") if row_class else ""
        classes = " ".join(filter(None, ["cfdb-linked" if row_href else "", extra]))
        body.append(f"<tr class='{classes}'>{joined}</tr>" if classes
                    else f"<tr>{joined}</tr>")
    # Set on the ROW, not per cell: it is the row's height that has to hold every header.
    head_style = f" style='height:{header_height}px'" if header_height else ""
    # 🚨 A189 (cfdb-main-R-1934). A TABLE WHOSE COLUMNS ARE ALL FIXED HAS AN EXACT WIDTH, AND
    # STRETCHING IT TO THE CONTAINER PUTS THE SLACK BACK.
    #
    # `.cfdb-table-wide` carries `min-width:100%`, which is right for a table whose columns are
    # weights — it stops a narrow table looking lost. 📊 But when every column is a measured
    # px, the extra width is shared out and lands as padding inside the cells: measured on
    # Most Exciting at 1440px, the scoreboard's slack went 49px -> **71px** with the fixed
    # widths in place, because the table grew to 1344px for columns summing to ~1250.
    #
    # ⚠️ DERIVED FROM THE LAYOUT, NOT A NEW ARGUMENT. A caller that has already said "every
    # column is this many pixels" has said everything needed; asking it to also pass
    # `stretch=False` is the opt-in this module distrusts (A141's eleven views).
    exact = bool(scroll and layout and all(str(w).endswith("px") for w in layout))
    table_css = ("cfdb-table" + (" cfdb-table-wide" if scroll else "")
                 + (" cfdb-table-exact" if exact else ""))
    markup = ("<table class='" + table_css + "'>"
              + (f"<caption>{caption}</caption>" if caption else "")
              + colgroup
              + f"<thead><tr{head_style}>{head}</tr></thead>"
              + f"<tbody>{''.join(body)}</tbody></table>")
    if scroll:
        # The scroll container is a WRAPPER, not the table: `overflow-x` on the table itself
        # does nothing, and putting it on an ancestor Streamlit owns is not ours to set.
        # A208: and the wrapper says so, at this table's own boundary. `exact` above has
        # already asked whether every column is a measured px — the same question, which is
        # why the note appears on exactly the tables whose width is theirs to state.
        markup = scroll_box(markup, scroll_minimum(layout))
    st.markdown(markup, unsafe_allow_html=True)
    if len(df) > max_rows:
        st.caption(f"Showing {max_rows:,} of {len(df):,} rows.")


def team_cell(row, slug_field: str, display_field: str, logo_field: str,
              rank_field: Optional[str] = None, logo_px: int = 28) -> str:
    """Logo-or-monogram plus name, with a rank badge only when the team is ranked.

    AC-1.5: an unranked team shows NO badge, not an em dash inside one.

    🚨 A213 (cfdb-main-R-2545). `logo_px` EXISTS BECAUSE A CSS RULE CANNOT REACH THIS LOGO.
    `identity.logo_or_monogram` emits its size as an INLINE STYLE on both branches, and an
    inline style beats every selector at every specificity short of `!important`. So
    `theme.py`'s `.cfdb-card-team .cfdb-logo-box { width:18px }` was never losing a
    specificity contest — **it was never in the contest**, and the player cards drew a 28px
    disc in a 44px track for six rounds while that rule sat there looking like the answer.

    ⚠️ THE DEFAULT IS 28 AND EVERY EXISTING CALLER IS UNTOUCHED (§3 rule 3.1 — a shared-module
    change ships the parameter and the default). The one caller that wants something else
    passes it: `today._player_card` -> `_team_identity` -> here. **Do not change
    `logo_or_monogram`'s own default** — `matchup.py` calls it directly at four sites, one of
    them already passing 14, and `team.py` passes 44.

    The slug_field argument was accepted and ignored for weeks, which is why every team
    name on the site was inert text. It is now what the anchor is built from — see
    `team_link` for the href, which is passed as the column's own `link` so the team name
    goes to the team and the rest of the row goes to the game.
    """
    # 🚨 A191 (cfdb-main-R-2001). `or "—"` DOES NOT CATCH A MISSING VALUE IN A DataFrame,
    # BECAUSE A FLOAT `NaN` IS TRUTHY. Today's week-average row printed the literal string
    # `nan` in its Opponent cell for exactly this reason — the em-dash fallback written for
    # the absent case was one truthiness test away from firing and never did.
    #
    # ⚠️ THE `rank` BRANCH ON THE NEXT LINE ALREADY GOT THIS RIGHT (`not pd.isna(rank)`), which
    # is what makes the name branch a defect rather than a design: two absence tests in one
    # function, disagreeing about what absence is.
    display = row.get(display_field)
    if display is None or (isinstance(display, float) and pd.isna(display)):
        display = None
    logo = identity.logo_or_monogram(row.get(logo_field), display or "?", logo_px)
    rank = row.get(rank_field) if rank_field else None
    badge = (f"<span class='cfdb-rank'>#{int(rank)}</span>"
             if rank is not None and not pd.isna(rank) else "")
    return f"{logo}{badge}<span class='cfdb-team'>{display or '—'}</span>"


def record_span(row, before_field: str, after_field: Optional[str] = None,
                completed_field: str = "is_completed") -> str:
    """The record, on its own — MOVED HERE FROM `schedule.py` BY A144, not reimplemented.

    🚨 R-129 IS WHY THIS IS SEPARABLE FROM `team_cell` RATHER THAN PART OF IT. Schedule's own
    comment: *"the record leaves the anchor entirely rather than being styled to look
    non-clickable — styling cannot remove the pointer cursor, and dead text under a pointer is
    worse than either state."* So a caller that links the team name puts THIS outside the anchor.
    Folding it into `team_cell` would put it inside one on every page that links.

    🚨 R-140 TRAVELS WITH IT, AND IT IS THE WHOLE REASON THIS IS A FUNCTION. *A COMPLETED GAME
    SHOWS THE RECORD IT PRODUCED; A SCHEDULED ONE SHOWS THE RECORD THE TEAM CARRIES IN.* Two
    columns, one slot, chosen by whether the game has been played — which is the only reading of
    Marc's sentence that can be true, since a record "after the game" cannot exist for a game
    nobody has played.

    ⚠️ BOTH COLUMNS ARE POINT-IN-TIME AND NEITHER IS THE SEASON-FINAL RECORD. `srv_game`'s own
    comment: *"R-084. THE RECORD AS IT STOOD GOING INTO THIS GAME'S WEEK"* — built on
    `fct_team_record_week`'s `rows between unbounded preceding and 1 preceding` frame. 📊 A144
    measured it rather than trusting the source column's NAME: across 2026 regular, all 453 week-1
    games carry `0-0`, one distinct value. A current-as-of-now record could not do that.

    ⚠️ `after_field` IS OPTIONAL BECAUSE NOT EVERY RELATION PUBLISHES THE PAIR.
    `srv_game_team` carries `record_before_display` alone — and names it that way as its own
    guard: *"on a game x team row a bare [record] is ambiguous"*. With no after-column the
    before-record is shown whatever the state, which is the honest answer rather than a blank.

    Renders NOTHING when the record is absent rather than substituting a season figure (R-084),
    and after R-127 "absent" means a team we hold no results for, not a team whose season has not
    started.
    """
    if after_field and row.get(completed_field):
        record, title = row.get(after_field), "record after this game"
    else:
        record, title = row.get(before_field), "record going into this game"
    if record is None or (not isinstance(record, str) and pd.isna(record)) or record == "":
        return ""
    return f"<span class='cfdb-team-record' title='{title}'>{record}</span>"


def team_link(slug_field: str, season_field: str = "season") -> Callable:
    """An href to a team page, for use as a Col's `link`.

    Returns None where the slug is missing rather than building `/team?team=None` — a link
    to nowhere is worse than a cell that was never clickable, which is the same reasoning
    that put a slug fallback on every serving view.
    """
    def href(row):
        slug = row.get(slug_field)
        if slug is None or (isinstance(slug, float) and pd.isna(slug)):
            return None
        season = row.get(season_field)
        query = f"team={slug}"
        if season is not None and not pd.isna(season):
            query += f"&season={int(season)}"
        return f"/team?{query}"
    return href


DETAILS_GLYPH = "▤"


def details_col(link_builder, label: str = "") -> "Col":
    """An explicit "open the detail page" cell.

    Both destinations already existed on a Schedule row — the row went to the game, the team
    name went to the team — and a reader could not tell them apart, which is why Marc
    proposed collapsing them into one. Collapsing would have made the Team page unreachable
    from the two most-visited pages on the site.

    An explicit affordance fixes discoverability instead. AC-2.5 requires the two to be
    "visually distinct"; a glyph in its own column is what makes that true rather than
    asserted.
    """
    return Col("details", label,
               render=lambda r: f"<span class='cfdb-details' title='Open the matchup'>"
                                f"{DETAILS_GLYPH}</span>",
               link=link_builder)


def dataset_caption(label: str, table_name: str) -> None:
    """AC-G.7, amended: front of house says "Dataset: Schedule", not `srv_game`.

    The literal object name is right for a BUILDER — System Overview and Degraded states
    keep it, because there the exact identifier is the point. On a page whose reader wants
    to know what they are looking at, a table name is jargon, and the useful move is a link
    to what that dataset actually contains.
    """
    # The link carries the TABLE, and the Data Dictionary reads it as a filter so the
    # reader lands on that table rather than the top of a 1,200-row page. `table` is the
    # canonical parameter name; `stat` was the wrong one and is why these did not resolve.
    st.markdown(
        f"<div class='cfdb-dataset'>Dataset: "
        f"<a href='/dictionary?table={table_name}' target='_self'>{label}</a>"
        f"</div>", unsafe_allow_html=True)


def as_of_caption(df: pd.DataFrame) -> None:
    """AC-G.35: every page states when its own data was loaded.

    R-158: rendered into Band 1's placeholder when the page has reserved one, so the stamp
    sits beside the status instead of costing a full-width row of its own. A page that has not
    been reorganised has no slot and gets the caption where it always was — the fallback is
    what keeps this a one-page change rather than an eighteen-page one.
    """
    if df is None or df.empty or "as_of_ts" not in df.columns:
        return
    text = fmt.as_of(df["as_of_ts"].max())
    from lib import shell
    slot = shell.as_of_slot()
    if slot is not None:
        slot.markdown(f"<div class='cfdb-asof-inline'>{text}</div>", unsafe_allow_html=True)
    else:
        st.caption(text)
