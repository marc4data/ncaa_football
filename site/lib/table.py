"""One table renderer, so eighteen pages format numbers the same way.

Formatting only. Every value arrives already computed — this decides how it looks, never
what it is (G-3). A column spec is declarative so a page says what a column MEANS and the
renderer decides precision, alignment and chip treatment from that.
"""
import re
from typing import Callable, List, Optional

import pandas as pd
import streamlit as st

from lib import chips, fmt, identity, params


class Col:
    """One column: where it comes from, what it is, and how it should read."""

    def __init__(self, field: str, label: str, kind: str = "text",
                 dp: Optional[int] = None, width: Optional[str] = None,
                 render: Optional[Callable] = None,
                 link: Optional[Callable] = None):
        self.field, self.label, self.kind = field, label, kind
        self.dp, self.width, self.render = dp, width, render
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


def apply_sort(df: pd.DataFrame, columns: List[Col],
               default: Optional[str] = None) -> pd.DataFrame:
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
    field = params.get("sort") or default
    if not field:
        return df
    if field not in df.columns:
        # A stale or hand-edited ?sort= names a column this table does not have. Ignore it
        # rather than raising: an unknown sort is noise, not a request (AC-G.11).
        return df
    ascending = (params.get("order") or "asc") == "asc"
    # na_position last in both directions: a null is not the smallest value, it is the
    # absence of one, and burying them keeps the top of the table meaningful either way.
    return df.sort_values(field, ascending=ascending, na_position="last",
                          kind="mergesort")


def _header_cell(column: Col, sortable: bool, freeze: str = "") -> str:
    """A header, and a sort toggle where the column has something to sort by."""
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
        return f"<th class='{column.css}{freeze}'>{column.label}</th>"

    current = params.get("sort")
    order = params.get("order") or "asc"
    is_active = current == column.field
    # Clicking the active column flips it; clicking a new one starts ascending.
    next_order = "desc" if (is_active and order == "asc") else "asc"
    arrow = ("▲" if order == "asc" else "▼") if is_active else "⇅"
    href = params.link_here(sort=column.field, order=next_order)
    active = " cfdb-sorted" if is_active else ""
    return (f"<th class='{column.css}{active}{freeze}'>"
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
           header_height: Optional[int] = None) -> None:
    """An HTML table, because Streamlit's dataframe cannot hold a chip or a link.

    AC-G.47: the table carries header semantics and a caption naming its source view.

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

    head = "".join(_header_cell(c, sortable, freeze(i))
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
    table_css = "cfdb-table" + (" cfdb-table-wide" if scroll else "")
    markup = ("<table class='" + table_css + "'>"
              + (f"<caption>{caption}</caption>" if caption else "")
              + colgroup
              + f"<thead><tr{head_style}>{head}</tr></thead>"
              + f"<tbody>{''.join(body)}</tbody></table>")
    if scroll:
        # The scroll container is a WRAPPER, not the table: `overflow-x` on the table itself
        # does nothing, and putting it on an ancestor Streamlit owns is not ours to set.
        markup = f"<div class='cfdb-scroll'>{markup}</div>"
    st.markdown(markup, unsafe_allow_html=True)
    if len(df) > max_rows:
        st.caption(f"Showing {max_rows:,} of {len(df):,} rows.")


def team_cell(row, slug_field: str, display_field: str, logo_field: str,
              rank_field: Optional[str] = None) -> str:
    """Logo-or-monogram plus name, with a rank badge only when the team is ranked.

    AC-1.5: an unranked team shows NO badge, not an em dash inside one.

    The slug_field argument was accepted and ignored for weeks, which is why every team
    name on the site was inert text. It is now what the anchor is built from — see
    `team_link` for the href, which is passed as the column's own `link` so the team name
    goes to the team and the rest of the row goes to the game.
    """
    logo = identity.logo_or_monogram(row.get(logo_field), row.get(display_field) or "?")
    rank = row.get(rank_field) if rank_field else None
    badge = (f"<span class='cfdb-rank'>#{int(rank)}</span>"
             if rank is not None and not pd.isna(rank) else "")
    return f"{logo}{badge}<span class='cfdb-team'>{row.get(display_field) or '—'}</span>"


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
